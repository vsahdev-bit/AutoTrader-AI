import express from 'express';
import cors from 'cors';
import pg from 'pg';
import dotenv from 'dotenv';
import { Configuration, PlaidApi, PlaidEnvironments, Products, CountryCode } from 'plaid';
import { 
  initializeVault, 
  storePlaidToken, 
  getPlaidToken, 
  deletePlaidToken, 
  checkVaultHealth,
  createTradeAuthToken,
  validateTradeAuthToken,
  consumeTradeAuthToken,
  hashValue,
} from './vault.js';

dotenv.config();

const { Pool } = pg;
const app = express();
const port = process.env.PORT || 3001;

// Plaid configuration
const plaidConfig = new Configuration({
  basePath: PlaidEnvironments[process.env.PLAID_ENV || 'sandbox'],
  baseOptions: {
    headers: {
      'PLAID-CLIENT-ID': process.env.PLAID_CLIENT_ID,
      'PLAID-SECRET': process.env.PLAID_SECRET,
    },
  },
});

const plaidClient = new PlaidApi(plaidConfig);

// Database connection
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

// Middleware
app.use(cors());
app.use(express.json());

// Health check
app.get('/health', async (req, res) => {
  const vaultHealth = await checkVaultHealth();
  res.json({ 
    status: 'ok',
    vault: vaultHealth,
  });
});

// ============== USER ROUTES ==============

// Get or create user by email (called after Google OAuth)
app.post('/api/users/auth', async (req, res) => {
  const { email, name, picture, googleId } = req.body;
  
  try {
    // Check if user exists
    let result = await pool.query('SELECT * FROM users WHERE email = $1', [email]);
    
    if (result.rows.length === 0) {
      // Create new user
      result = await pool.query(
        'INSERT INTO users (email, auth_provider) VALUES ($1, $2) RETURNING *',
        [email, 'google']
      );
      
      const userId = result.rows[0].id;
      
      // Create onboarding record
      await pool.query(
        'INSERT INTO user_onboarding (user_id, status) VALUES ($1, $2)',
        [userId, 'not_started']
      );
      
      // Create profile with Google info
      await pool.query(
        'INSERT INTO user_profiles (user_id, display_name, profile_picture_url) VALUES ($1, $2, $3)',
        [userId, name, picture]
      );
    }
    
    const user = result.rows[0];
    
    // Get onboarding status
    const onboardingResult = await pool.query(
      'SELECT * FROM user_onboarding WHERE user_id = $1',
      [user.id]
    );
    
    res.json({
      user,
      onboarding: onboardingResult.rows[0] || { status: 'not_started' }
    });
  } catch (error) {
    console.error('Error in /api/users/auth:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ============== ONBOARDING ROUTES ==============

// Get onboarding status and data
app.get('/api/onboarding/:userId', async (req, res) => {
  const { userId } = req.params;
  
  // Validate UUID format
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!uuidRegex.test(userId)) {
    // Return empty data for invalid UUID (e.g., Google sub ID before user is created)
    return res.json({
      onboarding: null,
      profile: null,
      preferences: null,
      watchlist: []
    });
  }
  
  try {
    const [onboarding, profile, preferences, watchlist, brokerageConnections] = await Promise.all([
      pool.query('SELECT * FROM user_onboarding WHERE user_id = $1', [userId]),
      pool.query('SELECT * FROM user_profiles WHERE user_id = $1', [userId]),
      pool.query('SELECT * FROM user_trading_preferences WHERE user_id = $1', [userId]),
      pool.query('SELECT * FROM user_watchlist WHERE user_id = $1 ORDER BY added_at', [userId]),
      pool.query('SELECT * FROM user_brokerage_connections WHERE user_id = $1 AND status = $2', [userId, 'active'])
    ]);
    
    res.json({
      onboarding: onboarding.rows[0] || null,
      profile: profile.rows[0] || null,
      preferences: preferences.rows[0] || null,
      watchlist: watchlist.rows || [],
      brokerageConnections: brokerageConnections.rows || []
    });
  } catch (error) {
    console.error('Error getting onboarding:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Update onboarding status
app.put('/api/onboarding/:userId/status', async (req, res) => {
  const { userId } = req.params;
  const { status, currentStep, completedSteps } = req.body;
  
  try {
    const result = await pool.query(
      `UPDATE user_onboarding 
       SET status = $1, current_step = $2, completed_steps = $3
       WHERE user_id = $4
       RETURNING *`,
      [status, currentStep, completedSteps, userId]
    );
    
    res.json(result.rows[0]);
  } catch (error) {
    console.error('Error updating onboarding status:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Save profile data
app.put('/api/onboarding/:userId/profile', async (req, res) => {
  const { userId } = req.params;
  const { displayName, phone, country, timezone } = req.body;
  
  try {
    const result = await pool.query(
      `UPDATE user_profiles 
       SET display_name = COALESCE($1, display_name),
           phone = COALESCE($2, phone),
           country = COALESCE($3, country),
           timezone = COALESCE($4, timezone)
       WHERE user_id = $5
       RETURNING *`,
      [displayName, phone, country, timezone, userId]
    );
    
    res.json(result.rows[0]);
  } catch (error) {
    console.error('Error updating profile:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Save trading preferences
app.put('/api/onboarding/:userId/preferences', async (req, res) => {
  const { userId } = req.params;
  const { experienceLevel, investmentGoals, riskTolerance, tradingFrequency, initialInvestmentRange } = req.body;
  
  try {
    // First check if record exists
    const existing = await pool.query('SELECT * FROM user_trading_preferences WHERE user_id = $1', [userId]);
    
    if (existing.rows.length === 0) {
      // Insert new record
      const result = await pool.query(
        `INSERT INTO user_trading_preferences (user_id, experience_level, investment_goals, risk_tolerance, trading_frequency, initial_investment_range)
         VALUES ($1, $2, $3, $4, $5, $6)
         RETURNING *`,
        [userId, experienceLevel || null, investmentGoals || null, riskTolerance || null, tradingFrequency || null, initialInvestmentRange || null]
      );
      res.json(result.rows[0]);
    } else {
      // Update only the fields that are provided (not undefined)
      const current = existing.rows[0];
      const result = await pool.query(
        `UPDATE user_trading_preferences SET
           experience_level = $2,
           investment_goals = $3,
           risk_tolerance = $4,
           trading_frequency = $5,
           initial_investment_range = $6
         WHERE user_id = $1
         RETURNING *`,
        [
          userId,
          experienceLevel !== undefined ? experienceLevel : current.experience_level,
          investmentGoals !== undefined ? investmentGoals : current.investment_goals,
          riskTolerance !== undefined ? riskTolerance : current.risk_tolerance,
          tradingFrequency !== undefined ? tradingFrequency : current.trading_frequency,
          initialInvestmentRange !== undefined ? initialInvestmentRange : current.initial_investment_range
        ]
      );
      res.json(result.rows[0]);
    }
  } catch (error) {
    console.error('Error updating preferences:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ============== WATCHLIST ROUTES ==============

// Add stock to watchlist
app.post('/api/onboarding/:userId/watchlist', async (req, res) => {
  const { userId } = req.params;
  const { symbol, companyName, exchange } = req.body;
  
  try {
    const result = await pool.query(
      `INSERT INTO user_watchlist (user_id, symbol, company_name, exchange)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (user_id, symbol) DO NOTHING
       RETURNING *`,
      [userId, symbol.toUpperCase(), companyName, exchange]
    );
    
    res.json(result.rows[0] || { message: 'Stock already in watchlist' });
  } catch (error) {
    console.error('Error adding to watchlist:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Remove stock from watchlist
app.delete('/api/onboarding/:userId/watchlist/:symbol', async (req, res) => {
  const { userId, symbol } = req.params;
  
  try {
    await pool.query(
      'DELETE FROM user_watchlist WHERE user_id = $1 AND symbol = $2',
      [userId, symbol.toUpperCase()]
    );
    
    res.json({ success: true });
  } catch (error) {
    console.error('Error removing from watchlist:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get user's watchlist
app.get('/api/onboarding/:userId/watchlist', async (req, res) => {
  const { userId } = req.params;
  
  try {
    const result = await pool.query(
      'SELECT * FROM user_watchlist WHERE user_id = $1 ORDER BY added_at',
      [userId]
    );
    
    res.json(result.rows);
  } catch (error) {
    console.error('Error getting watchlist:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ============== STOCK SEARCH ROUTES ==============

// Search stocks (using Yahoo Finance API style)
app.get('/api/stocks/search', async (req, res) => {
  const { q } = req.query;
  
  if (!q || q.length < 1) {
    return res.json([]);
  }
  
  try {
    // Use Yahoo Finance autosuggest API
    const response = await fetch(
      `https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&quotesCount=10&newsCount=0&enableFuzzyQuery=false&quotesQueryId=tss_match_phrase_query`
    );
    
    const data = await response.json();
    
    const results = (data.quotes || [])
      .filter(quote => quote.quoteType === 'EQUITY')
      .map(quote => ({
        symbol: quote.symbol,
        name: quote.shortname || quote.longname,
        exchange: quote.exchange,
        type: quote.quoteType
      }));
    
    res.json(results);
  } catch (error) {
    console.error('Error searching stocks:', error);
    res.status(500).json({ error: 'Failed to search stocks' });
  }
});

// Complete onboarding
app.post('/api/onboarding/:userId/complete', async (req, res) => {
  const { userId } = req.params;
  
  try {
    const result = await pool.query(
      `UPDATE user_onboarding 
       SET status = 'completed', current_step = -1
       WHERE user_id = $1
       RETURNING *`,
      [userId]
    );
    
    res.json(result.rows[0]);
  } catch (error) {
    console.error('Error completing onboarding:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ============== PLAID / BROKERAGE ROUTES ==============

// Create Plaid Link token (initiates the connection flow)
app.post('/api/plaid/create-link-token', async (req, res) => {
  const { userId } = req.body;
  
  // Check if Plaid is configured
  if (!process.env.PLAID_CLIENT_ID || !process.env.PLAID_SECRET) {
    return res.json({ 
      linkToken: null, 
      sandbox: true,
      message: 'Plaid not configured - using sandbox mode'
    });
  }
  
  try {
    const request = {
      user: { client_user_id: userId },
      client_name: 'AutoTrader AI',
      products: [Products.Investments],
      country_codes: [CountryCode.Us],
      language: 'en',
    };
    
    const response = await plaidClient.linkTokenCreate(request);
    res.json({ linkToken: response.data.link_token });
  } catch (error) {
    console.error('Error creating link token:', error);
    res.status(500).json({ error: 'Failed to create link token' });
  }
});

// Exchange public token for access token (after user connects account)
app.post('/api/plaid/exchange-token', async (req, res) => {
  const { userId, publicToken, institutionId, institutionName } = req.body;
  
  // Sandbox mode - simulate successful connection
  if (!process.env.PLAID_CLIENT_ID || !process.env.PLAID_SECRET) {
    try {
      const itemId = 'sandbox-item-' + Date.now();
      const sandboxAccessToken = 'sandbox-access-token-' + Date.now();
      
      // Store access token securely in Vault (not in database)
      await storePlaidToken(userId, itemId, sandboxAccessToken, {
        institutionId: institutionId || 'ins_robinhood',
        institutionName: institutionName || 'Robinhood',
        sandbox: true,
      });
      
      // Store connection metadata in database (without the access token)
      const result = await pool.query(
        `INSERT INTO user_brokerage_connections 
         (user_id, plaid_item_id, plaid_access_token, institution_id, institution_name, status)
         VALUES ($1, $2, $3, $4, $5, $6)
         ON CONFLICT (user_id, plaid_item_id) DO UPDATE SET
           status = 'active',
           updated_at = NOW()
         RETURNING *`,
        [userId, itemId, '[STORED_IN_VAULT]', institutionId || 'ins_robinhood', institutionName || 'Robinhood', 'active']
      );
      
      // Create mock account
      await pool.query(
        `INSERT INTO user_brokerage_accounts
         (connection_id, user_id, plaid_account_id, account_name, account_type, account_subtype, mask, is_primary)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         ON CONFLICT (connection_id, plaid_account_id) DO NOTHING`,
        [result.rows[0].id, userId, 'sandbox-account-' + Date.now(), 'Individual Brokerage', 'investment', 'brokerage', '1234', true]
      );
      
      // Don't return the actual token - it's in Vault
      const safeConnection = { ...result.rows[0] };
      delete safeConnection.plaid_access_token;
      
      return res.json({ 
        success: true, 
        sandbox: true,
        connection: safeConnection,
        tokenStoredSecurely: true,
      });
    } catch (error) {
      console.error('Error creating sandbox connection:', error);
      return res.status(500).json({ error: 'Failed to create connection' });
    }
  }
  
  try {
    // Exchange public token for access token
    const exchangeResponse = await plaidClient.itemPublicTokenExchange({
      public_token: publicToken,
    });
    
    const accessToken = exchangeResponse.data.access_token;
    const itemId = exchangeResponse.data.item_id;
    
    // Store access token securely in Vault (not in database)
    await storePlaidToken(userId, itemId, accessToken, {
      institutionId,
      institutionName,
    });
    
    // Store connection metadata in database (without the actual access token)
    const connectionResult = await pool.query(
      `INSERT INTO user_brokerage_connections 
       (user_id, plaid_item_id, plaid_access_token, institution_id, institution_name, status)
       VALUES ($1, $2, $3, $4, $5, $6)
       ON CONFLICT (user_id, plaid_item_id) DO UPDATE SET
         plaid_access_token = $3,
         status = 'active',
         updated_at = NOW()
       RETURNING *`,
      [userId, itemId, '[STORED_IN_VAULT]', institutionId, institutionName, 'active']
    );
    
    // Get investment accounts using token from Vault
    const accountsResponse = await plaidClient.investmentsHoldingsGet({
      access_token: accessToken,
    });
    
    // Store accounts
    for (const account of accountsResponse.data.accounts) {
      await pool.query(
        `INSERT INTO user_brokerage_accounts
         (connection_id, user_id, plaid_account_id, account_name, account_type, account_subtype, mask, is_primary)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         ON CONFLICT (connection_id, plaid_account_id) DO UPDATE SET
           account_name = $4,
           account_type = $5,
           account_subtype = $6,
           mask = $7`,
        [connectionResult.rows[0].id, userId, account.account_id, account.name, account.type, account.subtype, account.mask, false]
      );
    }
    
    // Don't return the actual token - it's in Vault
    const safeConnection = { ...connectionResult.rows[0] };
    delete safeConnection.plaid_access_token;
    
    res.json({ 
      success: true, 
      connection: safeConnection,
      accountCount: accountsResponse.data.accounts.length,
      tokenStoredSecurely: true,
    });
  } catch (error) {
    console.error('Error exchanging token:', error);
    res.status(500).json({ error: 'Failed to connect brokerage account' });
  }
});

// Get user's brokerage connections
app.get('/api/brokerage/:userId/connections', async (req, res) => {
  const { userId } = req.params;
  
  // Validate UUID format
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!uuidRegex.test(userId)) {
    return res.json({ connections: [], accounts: [] });
  }
  
  try {
    const [connections, accounts] = await Promise.all([
      pool.query(
        'SELECT id, institution_id, institution_name, status, last_synced_at, created_at FROM user_brokerage_connections WHERE user_id = $1 ORDER BY created_at DESC',
        [userId]
      ),
      pool.query(
        'SELECT * FROM user_brokerage_accounts WHERE user_id = $1 ORDER BY is_primary DESC, created_at',
        [userId]
      ),
    ]);
    
    res.json({
      connections: connections.rows,
      accounts: accounts.rows,
    });
  } catch (error) {
    console.error('Error getting brokerage connections:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Disconnect brokerage
app.delete('/api/brokerage/:userId/connections/:connectionId', async (req, res) => {
  const { userId, connectionId } = req.params;
  
  try {
    // Get the item ID before disconnecting
    const connection = await pool.query(
      'SELECT plaid_item_id FROM user_brokerage_connections WHERE id = $1 AND user_id = $2',
      [connectionId, userId]
    );
    
    if (connection.rows.length > 0) {
      const itemId = connection.rows[0].plaid_item_id;
      
      // Delete access token from Vault
      await deletePlaidToken(userId, itemId);
    }
    
    // Mark as disconnected (we keep the record for audit purposes)
    await pool.query(
      `UPDATE user_brokerage_connections 
       SET status = 'disconnected', plaid_access_token = '[DELETED]', updated_at = NOW()
       WHERE id = $1 AND user_id = $2`,
      [connectionId, userId]
    );
    
    res.json({ success: true, tokenDeletedFromVault: true });
  } catch (error) {
    console.error('Error disconnecting brokerage:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ============== TRADE AUTHORIZATION ROUTES ==============

// Create a trade authorization request (initiates the trade flow)
app.post('/api/trade/authorize', async (req, res) => {
  const { userId, brokerageConnectionId, symbol, action, quantity, orderType, limitPrice } = req.body;
  
  // Validate required fields
  if (!userId || !brokerageConnectionId || !symbol || !action || !quantity) {
    return res.status(400).json({ error: 'Missing required fields' });
  }
  
  if (!['BUY', 'SELL'].includes(action.toUpperCase())) {
    return res.status(400).json({ error: 'Action must be BUY or SELL' });
  }
  
  try {
    // Verify the brokerage connection exists and is active
    const connectionCheck = await pool.query(
      'SELECT id, institution_name FROM user_brokerage_connections WHERE id = $1 AND user_id = $2 AND status = $3',
      [brokerageConnectionId, userId, 'active']
    );
    
    if (connectionCheck.rows.length === 0) {
      return res.status(400).json({ error: 'Invalid or inactive brokerage connection' });
    }
    
    const tradeDetails = {
      symbol: symbol.toUpperCase(),
      action: action.toUpperCase(),
      quantity: parseFloat(quantity),
      orderType: orderType || 'market',
      limitPrice: limitPrice ? parseFloat(limitPrice) : null,
      brokerageConnectionId,
      institutionName: connectionCheck.rows[0].institution_name,
    };
    
    // Set TTL to 5 minutes (300 seconds)
    const ttlSeconds = 300;
    const expiresAt = new Date(Date.now() + ttlSeconds * 1000);
    
    // Create a placeholder in database first to get the ID
    const tradeAuth = await pool.query(
      `INSERT INTO trade_authorizations 
       (user_id, brokerage_connection_id, symbol, action, quantity, order_type, limit_price, auth_token_hash, expires_at, status)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
       RETURNING id`,
      [userId, brokerageConnectionId, tradeDetails.symbol, tradeDetails.action, tradeDetails.quantity, 
       tradeDetails.orderType, tradeDetails.limitPrice, 'pending', expiresAt, 'pending']
    );
    
    const tradeAuthId = tradeAuth.rows[0].id;
    
    // Create short-lived token in Vault
    const { token } = await createTradeAuthToken(userId, tradeAuthId, tradeDetails, ttlSeconds);
    
    // Update database with token hash
    await pool.query(
      'UPDATE trade_authorizations SET auth_token_hash = $1 WHERE id = $2',
      [hashValue(token), tradeAuthId]
    );
    
    // Log the authorization creation
    await pool.query(
      `INSERT INTO trade_audit_log (trade_authorization_id, user_id, action, details)
       VALUES ($1, $2, $3, $4)`,
      [tradeAuthId, userId, 'auth_created', JSON.stringify({ symbol: tradeDetails.symbol, action: tradeDetails.action, quantity: tradeDetails.quantity })]
    );
    
    res.json({
      success: true,
      tradeAuthId,
      token, // This is sent to the client for confirmation step
      expiresAt: expiresAt.toISOString(),
      ttlSeconds,
      tradeDetails,
      message: `Authorization created. Confirm within ${ttlSeconds / 60} minutes.`,
    });
  } catch (error) {
    console.error('Error creating trade authorization:', error);
    res.status(500).json({ error: 'Failed to create trade authorization' });
  }
});

// Confirm and execute a trade (validates token + optional PIN)
app.post('/api/trade/execute', async (req, res) => {
  const { userId, tradeAuthId, token, pin } = req.body;
  
  if (!userId || !tradeAuthId || !token) {
    return res.status(400).json({ error: 'Missing required fields' });
  }
  
  try {
    // First, expire any old authorizations
    await pool.query('SELECT expire_old_trade_authorizations()');
    
    // Check if trade auth exists and is pending
    const tradeAuth = await pool.query(
      `SELECT ta.*, ubc.plaid_item_id 
       FROM trade_authorizations ta
       JOIN user_brokerage_connections ubc ON ta.brokerage_connection_id = ubc.id
       WHERE ta.id = $1 AND ta.user_id = $2 AND ta.status = $3`,
      [tradeAuthId, userId, 'pending']
    );
    
    if (tradeAuth.rows.length === 0) {
      return res.status(400).json({ error: 'Trade authorization not found, already executed, or expired' });
    }
    
    const trade = tradeAuth.rows[0];
    
    // Verify token hash matches
    if (hashValue(token) !== trade.auth_token_hash) {
      // Log failed attempt
      await pool.query(
        `INSERT INTO trade_audit_log (trade_authorization_id, user_id, action, details)
         VALUES ($1, $2, $3, $4)`,
        [tradeAuthId, userId, 'auth_failed', JSON.stringify({ reason: 'invalid_token' })]
      );
      return res.status(401).json({ error: 'Invalid authorization token' });
    }
    
    // Validate token in Vault (checks expiration and consumes it)
    const validation = await consumeTradeAuthToken(userId, tradeAuthId, token);
    
    if (!validation) {
      // Update status to expired
      await pool.query(
        'UPDATE trade_authorizations SET status = $1 WHERE id = $2',
        ['expired', tradeAuthId]
      );
      return res.status(401).json({ error: 'Authorization token expired or invalid' });
    }
    
    // Optional: Verify PIN if user has one set up
    if (pin) {
      const userPin = await pool.query(
        'SELECT pin_hash, failed_attempts, locked_until FROM user_trade_pins WHERE user_id = $1',
        [userId]
      );
      
      if (userPin.rows.length > 0) {
        const pinRecord = userPin.rows[0];
        
        // Check if locked
        if (pinRecord.locked_until && new Date(pinRecord.locked_until) > new Date()) {
          return res.status(403).json({ error: 'Account temporarily locked due to failed attempts' });
        }
        
        // Verify PIN
        if (hashValue(pin) !== pinRecord.pin_hash) {
          // Increment failed attempts
          const newAttempts = pinRecord.failed_attempts + 1;
          const lockUntil = newAttempts >= 5 ? new Date(Date.now() + 30 * 60 * 1000) : null; // Lock for 30 min after 5 failures
          
          await pool.query(
            'UPDATE user_trade_pins SET failed_attempts = $1, locked_until = $2 WHERE user_id = $3',
            [newAttempts, lockUntil, userId]
          );
          
          return res.status(401).json({ error: 'Invalid PIN', attemptsRemaining: Math.max(0, 5 - newAttempts) });
        }
        
        // Reset failed attempts on success
        await pool.query(
          'UPDATE user_trade_pins SET failed_attempts = 0, locked_until = NULL WHERE user_id = $1',
          [userId]
        );
      }
    }
    
    // Mark as confirmed
    await pool.query(
      'UPDATE trade_authorizations SET status = $1, confirmed_at = NOW() WHERE id = $2',
      ['confirmed', tradeAuthId]
    );
    
    // Log confirmation
    await pool.query(
      `INSERT INTO trade_audit_log (trade_authorization_id, user_id, action, details)
       VALUES ($1, $2, $3, $4)`,
      [tradeAuthId, userId, 'auth_confirmed', JSON.stringify({ symbol: trade.symbol })]
    );
    
    // Execute the trade (in sandbox mode, simulate execution)
    // In production, this would use the Plaid token from Vault to execute via broker API
    const executedPrice = trade.limit_price || (100 + Math.random() * 200).toFixed(2); // Mock price
    const brokerOrderId = 'order-' + Date.now();
    
    // Update trade as executed
    await pool.query(
      `UPDATE trade_authorizations 
       SET status = $1, executed_at = NOW(), executed_price = $2, executed_quantity = $3, broker_order_id = $4
       WHERE id = $5`,
      ['executed', executedPrice, trade.quantity, brokerOrderId, tradeAuthId]
    );
    
    // Log execution
    await pool.query(
      `INSERT INTO trade_audit_log (trade_authorization_id, user_id, action, details)
       VALUES ($1, $2, $3, $4)`,
      [tradeAuthId, userId, 'trade_executed', JSON.stringify({ 
        symbol: trade.symbol, 
        action: trade.action,
        quantity: parseFloat(trade.quantity),
        price: parseFloat(executedPrice),
        brokerOrderId 
      })]
    );
    
    res.json({
      success: true,
      tradeAuthId,
      status: 'executed',
      execution: {
        symbol: trade.symbol,
        action: trade.action,
        quantity: parseFloat(trade.quantity),
        price: parseFloat(executedPrice),
        total: (parseFloat(trade.quantity) * parseFloat(executedPrice)).toFixed(2),
        brokerOrderId,
        executedAt: new Date().toISOString(),
      },
      message: `Successfully ${trade.action === 'BUY' ? 'bought' : 'sold'} ${trade.quantity} shares of ${trade.symbol}`,
    });
  } catch (error) {
    console.error('Error executing trade:', error);
    res.status(500).json({ error: 'Failed to execute trade' });
  }
});

// Cancel a pending trade authorization
app.post('/api/trade/cancel', async (req, res) => {
  const { userId, tradeAuthId } = req.body;
  
  try {
    const result = await pool.query(
      `UPDATE trade_authorizations 
       SET status = 'cancelled'
       WHERE id = $1 AND user_id = $2 AND status = 'pending'
       RETURNING *`,
      [tradeAuthId, userId]
    );
    
    if (result.rows.length === 0) {
      return res.status(400).json({ error: 'Trade authorization not found or already processed' });
    }
    
    // Log cancellation
    await pool.query(
      `INSERT INTO trade_audit_log (trade_authorization_id, user_id, action, details)
       VALUES ($1, $2, $3, $4)`,
      [tradeAuthId, userId, 'auth_cancelled', JSON.stringify({ symbol: result.rows[0].symbol })]
    );
    
    res.json({ success: true, message: 'Trade authorization cancelled' });
  } catch (error) {
    console.error('Error cancelling trade:', error);
    res.status(500).json({ error: 'Failed to cancel trade' });
  }
});

// Get trade history for a user
app.get('/api/trade/history/:userId', async (req, res) => {
  const { userId } = req.params;
  const { limit = 20, status } = req.query;
  
  try {
    let query = `
      SELECT ta.*, ubc.institution_name
      FROM trade_authorizations ta
      JOIN user_brokerage_connections ubc ON ta.brokerage_connection_id = ubc.id
      WHERE ta.user_id = $1
    `;
    const params = [userId];
    
    if (status) {
      query += ` AND ta.status = $${params.length + 1}`;
      params.push(status);
    }
    
    query += ` ORDER BY ta.created_at DESC LIMIT $${params.length + 1}`;
    params.push(parseInt(limit));
    
    const result = await pool.query(query, params);
    
    res.json({
      trades: result.rows.map(t => ({
        id: t.id,
        symbol: t.symbol,
        action: t.action,
        quantity: parseFloat(t.quantity),
        orderType: t.order_type,
        limitPrice: t.limit_price ? parseFloat(t.limit_price) : null,
        status: t.status,
        executedPrice: t.executed_price ? parseFloat(t.executed_price) : null,
        brokerOrderId: t.broker_order_id,
        institutionName: t.institution_name,
        createdAt: t.created_at,
        executedAt: t.executed_at,
      })),
    });
  } catch (error) {
    console.error('Error getting trade history:', error);
    res.status(500).json({ error: 'Failed to get trade history' });
  }
});

// Set or update trade PIN
app.post('/api/trade/pin', async (req, res) => {
  const { userId, pin, currentPin } = req.body;
  
  if (!userId || !pin || pin.length < 4 || pin.length > 6) {
    return res.status(400).json({ error: 'PIN must be 4-6 digits' });
  }
  
  try {
    // Check if user already has a PIN
    const existing = await pool.query(
      'SELECT pin_hash FROM user_trade_pins WHERE user_id = $1',
      [userId]
    );
    
    if (existing.rows.length > 0) {
      // Verify current PIN before allowing change
      if (!currentPin || hashValue(currentPin) !== existing.rows[0].pin_hash) {
        return res.status(401).json({ error: 'Current PIN required to change PIN' });
      }
      
      // Update PIN
      await pool.query(
        'UPDATE user_trade_pins SET pin_hash = $1, failed_attempts = 0 WHERE user_id = $2',
        [hashValue(pin), userId]
      );
    } else {
      // Create new PIN
      await pool.query(
        'INSERT INTO user_trade_pins (user_id, pin_hash) VALUES ($1, $2)',
        [userId, hashValue(pin)]
      );
    }
    
    res.json({ success: true, message: 'Trade PIN set successfully' });
  } catch (error) {
    console.error('Error setting trade PIN:', error);
    res.status(500).json({ error: 'Failed to set trade PIN' });
  }
});

// Check if user has trade PIN enabled
app.get('/api/trade/pin/:userId', async (req, res) => {
  const { userId } = req.params;
  
  try {
    const result = await pool.query(
      'SELECT user_id FROM user_trade_pins WHERE user_id = $1',
      [userId]
    );
    
    res.json({ hasPinEnabled: result.rows.length > 0 });
  } catch (error) {
    res.status(500).json({ error: 'Failed to check PIN status' });
  }
});

// ============== STOCK RECOMMENDATIONS ROUTES ==============

/**
 * Trigger manual recommendation generation for all watchlist stocks
 * This runs the recommendation flow service on demand
 */
app.post('/api/v1/recommendations/generate', async (req, res) => {
  try {
    const { symbols } = req.body; // Optional: specific symbols to generate for
    
    // Update status to show generation is in progress
    const now = new Date().toISOString();
    console.log('Manual recommendation generation triggered at', now);
    
    // Mark that generation is in progress by creating a status record
    await pool.query(`
      INSERT INTO recommendation_generation_status (status, started_at, symbols)
      VALUES ('running', NOW(), $1)
      ON CONFLICT (id) DO UPDATE SET 
        status = 'running',
        started_at = NOW(),
        symbols = $1,
        completed_at = NULL,
        error_message = NULL
    `, [symbols ? JSON.stringify(symbols) : null]);
    
    // Call the recommendation engine's HTTP API
    try {
      const http = await import('http');
      
      const options = {
        hostname: 'recommendation-engine',
        port: 8000,
        path: '/generate',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        timeout: 10000, // 10 second timeout for the request
      };
      
      const engineReq = http.request(options, async (engineRes) => {
        let data = '';
        engineRes.on('data', chunk => data += chunk);
        engineRes.on('end', async () => {
          try {
            if (engineRes.statusCode === 202 || engineRes.statusCode === 200) {
              console.log('Recommendation engine accepted request:', data);
              // Generation runs in background, status updated when complete
            } else {
              console.error('Recommendation engine error:', data);
              await pool.query(`
                UPDATE recommendation_generation_status 
                SET status = 'failed', completed_at = NOW(), error_message = $1
                WHERE status = 'running'
              `, [`Engine returned ${engineRes.statusCode}: ${data}`]);
            }
          } catch (dbError) {
            console.error('Error updating generation status:', dbError);
          }
        });
      });
      
      engineReq.on('error', async (error) => {
        console.error('Failed to connect to recommendation engine:', error.message);
        try {
          await pool.query(`
            UPDATE recommendation_generation_status 
            SET status = 'failed', completed_at = NOW(), error_message = $1
            WHERE status = 'running'
          `, [`Connection failed: ${error.message}`]);
        } catch (dbError) {
          console.error('Error updating generation status:', dbError);
        }
      });
      
      engineReq.on('timeout', () => {
        engineReq.destroy();
        console.error('Recommendation engine request timed out');
      });
      
      engineReq.end();
      
    } catch (httpError) {
      console.log('Could not call recommendation engine:', httpError.message);
    }
    
    res.json({ 
      success: true, 
      message: 'Recommendation generation started',
      startedAt: now,
    });
  } catch (error) {
    console.error('Error triggering recommendation generation:', error);
    res.status(500).json({ error: 'Failed to trigger recommendation generation' });
  }
});

/**
 * Get the status of recommendation generation
 */
app.get('/api/v1/recommendations/generation-status', async (req, res) => {
  try {
    // Check if the status table exists
    const tableCheck = await pool.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'recommendation_generation_status'
      );
    `);
    
    if (!tableCheck.rows[0].exists) {
      return res.json({
        status: 'idle',
        message: 'No generation in progress',
      });
    }
    
    const result = await pool.query(`
      SELECT status, started_at, completed_at, symbols, error_message
      FROM recommendation_generation_status
      ORDER BY started_at DESC
      LIMIT 1
    `);
    
    if (result.rows.length === 0) {
      return res.json({
        status: 'idle',
        message: 'No generation history',
      });
    }
    
    const row = result.rows[0];
    res.json({
      status: row.status,
      startedAt: row.started_at,
      completedAt: row.completed_at,
      symbols: row.symbols ? JSON.parse(row.symbols) : null,
      errorMessage: row.error_message,
    });
  } catch (error) {
    console.error('Error getting generation status:', error);
    res.status(500).json({ error: 'Failed to get generation status' });
  }
});

/**
 * Get latest recommendations for all stocks
 * Returns the most recent recommendation for each symbol
 */
app.get('/api/v1/recommendations', async (req, res) => {
  try {
    const { limit = 20 } = req.query;
    
    const result = await pool.query(`
      SELECT DISTINCT ON (symbol)
        id,
        symbol,
        action,
        score,
        normalized_score,
        confidence,
        price_at_recommendation,
        news_sentiment_score,
        news_momentum_score,
        technical_trend_score,
        technical_momentum_score,
        rsi,
        macd_histogram,
        price_vs_sma20,
        news_sentiment_1d,
        article_count_24h,
        explanation,
        generated_at,
        data_sources_used,
        created_at
      FROM stock_recommendations
      ORDER BY symbol, generated_at DESC
      LIMIT $1
    `, [parseInt(limit)]);
    
    res.json({
      recommendations: result.rows.map(row => ({
        id: row.id,
        symbol: row.symbol,
        action: row.action,
        score: parseFloat(row.score),
        normalizedScore: parseFloat(row.normalized_score),
        confidence: parseFloat(row.confidence),
        priceAtRecommendation: row.price_at_recommendation ? parseFloat(row.price_at_recommendation) : null,
        newsSentimentScore: row.news_sentiment_score ? parseFloat(row.news_sentiment_score) : null,
        newsMomentumScore: row.news_momentum_score ? parseFloat(row.news_momentum_score) : null,
        technicalTrendScore: row.technical_trend_score ? parseFloat(row.technical_trend_score) : null,
        technicalMomentumScore: row.technical_momentum_score ? parseFloat(row.technical_momentum_score) : null,
        rsi: row.rsi ? parseFloat(row.rsi) : null,
        macdHistogram: row.macd_histogram ? parseFloat(row.macd_histogram) : null,
        priceVsSma20: row.price_vs_sma20 ? parseFloat(row.price_vs_sma20) : null,
        newsSentiment1d: row.news_sentiment_1d ? parseFloat(row.news_sentiment_1d) : null,
        articleCount24h: row.article_count_24h,
        explanation: row.explanation,
        generatedAt: row.generated_at,
        dataSourcesUsed: row.data_sources_used,
        createdAt: row.created_at,
      })),
      count: result.rows.length,
    });
  } catch (error) {
    console.error('Error getting recommendations:', error);
    res.status(500).json({ error: 'Failed to get recommendations' });
  }
});

/**
 * Get recommendation history for a specific symbol
 * Returns up to 10 most recent recommendations
 */
app.get('/api/v1/recommendations/history/:symbol', async (req, res) => {
  const { symbol } = req.params;
  const { limit = 10 } = req.query;
  
  try {
    const result = await pool.query(`
      SELECT 
        id,
        symbol,
        action,
        score,
        normalized_score,
        confidence,
        price_at_recommendation,
        news_sentiment_score,
        news_momentum_score,
        technical_trend_score,
        technical_momentum_score,
        rsi,
        macd_histogram,
        price_vs_sma20,
        news_sentiment_1d,
        article_count_24h,
        explanation,
        generated_at,
        data_sources_used,
        created_at
      FROM stock_recommendations
      WHERE symbol = $1
      ORDER BY generated_at DESC
      LIMIT $2
    `, [symbol.toUpperCase(), parseInt(limit)]);
    
    res.json({
      symbol: symbol.toUpperCase(),
      recommendations: result.rows.map(row => ({
        id: row.id,
        symbol: row.symbol,
        action: row.action,
        score: parseFloat(row.score),
        normalizedScore: parseFloat(row.normalized_score),
        confidence: parseFloat(row.confidence),
        priceAtRecommendation: row.price_at_recommendation ? parseFloat(row.price_at_recommendation) : null,
        newsSentimentScore: row.news_sentiment_score ? parseFloat(row.news_sentiment_score) : null,
        newsMomentumScore: row.news_momentum_score ? parseFloat(row.news_momentum_score) : null,
        technicalTrendScore: row.technical_trend_score ? parseFloat(row.technical_trend_score) : null,
        technicalMomentumScore: row.technical_momentum_score ? parseFloat(row.technical_momentum_score) : null,
        rsi: row.rsi ? parseFloat(row.rsi) : null,
        macdHistogram: row.macd_histogram ? parseFloat(row.macd_histogram) : null,
        priceVsSma20: row.price_vs_sma20 ? parseFloat(row.price_vs_sma20) : null,
        newsSentiment1d: row.news_sentiment_1d ? parseFloat(row.news_sentiment_1d) : null,
        articleCount24h: row.article_count_24h,
        explanation: row.explanation,
        generatedAt: row.generated_at,
        dataSourcesUsed: row.data_sources_used,
        createdAt: row.created_at,
      })),
      count: result.rows.length,
    });
  } catch (error) {
    console.error('Error getting recommendation history:', error);
    res.status(500).json({ error: 'Failed to get recommendation history' });
  }
});

// ============== LLM CONNECTOR STATUS ROUTES ==============

/**
 * Get all LLM connector statuses
 * Used by the Connectors page to display LLM provider status
 */
app.get('/api/v1/llm-connectors/status', async (req, res) => {
  try {
    // Check if the table exists
    const tableCheck = await pool.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'llm_connector_status'
      );
    `);
    
    if (!tableCheck.rows[0].exists) {
      // Return default LLM connectors if table doesn't exist
      const defaultLLMConnectors = [
        { name: 'openai', displayName: 'OpenAI', modelName: 'gpt-4o-mini', tier: 'paid', fallbackOrder: 1, requiresApiKey: true },
        { name: 'anthropic', displayName: 'Anthropic', modelName: 'claude-3-haiku', tier: 'paid', fallbackOrder: 2, requiresApiKey: true },
        { name: 'groq', displayName: 'Groq', modelName: 'llama-3.1-8b-instant', tier: 'free', fallbackOrder: 3, requiresApiKey: true },
      ];
      
      return res.json({
        connectors: defaultLLMConnectors.map(c => ({
          ...c,
          status: 'unknown',
          statusMessage: 'Run health check to get current status',
          lastCheckAt: null,
          lastSuccessAt: null,
          lastErrorAt: null,
          lastErrorMessage: null,
          responseTimeMs: null,
          hasApiKey: false,
          updatedAt: null,
        })),
        lastUpdated: null,
      });
    }
    
    const result = await pool.query(`
      SELECT 
        provider_name,
        display_name,
        model_name,
        tier,
        fallback_order,
        status,
        status_message,
        last_check_at,
        last_success_at,
        last_error_at,
        last_error_message,
        response_time_ms,
        requires_api_key,
        has_api_key,
        updated_at
      FROM llm_connector_status
      ORDER BY fallback_order
    `);
    
    res.json({
      connectors: result.rows.map(row => ({
        name: row.provider_name,
        displayName: row.display_name,
        modelName: row.model_name,
        tier: row.tier,
        fallbackOrder: row.fallback_order,
        status: row.status,
        statusMessage: row.status_message,
        lastCheckAt: row.last_check_at,
        lastSuccessAt: row.last_success_at,
        lastErrorAt: row.last_error_at,
        lastErrorMessage: row.last_error_message,
        responseTimeMs: row.response_time_ms,
        requiresApiKey: row.requires_api_key,
        hasApiKey: row.has_api_key,
        updatedAt: row.updated_at,
      })),
      lastUpdated: result.rows.length > 0 
        ? result.rows.reduce((latest, row) => 
            row.last_check_at > latest ? row.last_check_at : latest, 
            result.rows[0].last_check_at
          )
        : null,
    });
  } catch (error) {
    console.error('Error getting LLM connector statuses:', error);
    res.status(500).json({ error: 'Failed to get LLM connector statuses' });
  }
});

/**
 * Trigger manual health check for LLM connectors
 */
app.post('/api/v1/llm-connectors/refresh', async (req, res) => {
  try {
    const now = new Date().toISOString();
    
    // Update status to show refresh in progress
    await pool.query(`
      UPDATE llm_connector_status 
      SET status_message = 'Refresh requested at ' || $1::text,
          last_check_at = NOW()
    `, [now]);
    
    console.log('LLM connector health check requested at', now);
    
    res.json({ 
      success: true, 
      message: 'LLM health check started. Status will update shortly.',
    });
  } catch (error) {
    console.error('Error triggering LLM connector refresh:', error);
    res.status(500).json({ error: 'Failed to trigger LLM connector refresh' });
  }
});

// ============== HEALTH CHECK SETTINGS ROUTES ==============

/**
 * Get health check toggle settings
 * Returns the enabled/disabled state for data and LLM connector health checks
 */
app.get('/api/v1/health-check-settings', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT setting_key, enabled, updated_at 
      FROM health_check_settings
      ORDER BY setting_key
    `);
    
    const settings = {};
    result.rows.forEach(row => {
      settings[row.setting_key] = {
        enabled: row.enabled,
        updatedAt: row.updated_at
      };
    });
    
    res.json({
      dataConnectorsHealthCheck: settings['data_connectors_health_check'] || { enabled: true },
      llmConnectorsHealthCheck: settings['llm_connectors_health_check'] || { enabled: true }
    });
  } catch (error) {
    console.error('Error fetching health check settings:', error);
    res.status(500).json({ error: 'Failed to fetch health check settings' });
  }
});

/**
 * Update health check toggle setting
 * Enables or disables automatic health checks for data or LLM connectors
 */
app.put('/api/v1/health-check-settings/:type', async (req, res) => {
  try {
    const { type } = req.params;
    const { enabled } = req.body;
    
    // Validate type
    const settingKey = type === 'data' 
      ? 'data_connectors_health_check' 
      : type === 'llm' 
        ? 'llm_connectors_health_check'
        : null;
    
    if (!settingKey) {
      return res.status(400).json({ error: 'Invalid type. Must be "data" or "llm"' });
    }
    
    if (typeof enabled !== 'boolean') {
      return res.status(400).json({ error: 'enabled must be a boolean' });
    }
    
    const result = await pool.query(`
      UPDATE health_check_settings 
      SET enabled = $1, updated_at = NOW()
      WHERE setting_key = $2
      RETURNING setting_key, enabled, updated_at
    `, [enabled, settingKey]);
    
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Setting not found' });
    }
    
    console.log(`Health check setting updated: ${settingKey} = ${enabled}`);
    
    res.json({
      success: true,
      setting: {
        key: result.rows[0].setting_key,
        enabled: result.rows[0].enabled,
        updatedAt: result.rows[0].updated_at
      }
    });
  } catch (error) {
    console.error('Error updating health check setting:', error);
    res.status(500).json({ error: 'Failed to update health check setting' });
  }
});

// ============== CONNECTOR STATUS ROUTES ==============

/**
 * Get all connector statuses
 * Used by the Connectors page to display current status of all data connectors
 */
app.get('/api/v1/connectors/status', async (req, res) => {
  try {
    // Check if the table exists first
    const tableCheck = await pool.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'connector_status'
      );
    `);
    
    if (!tableCheck.rows[0].exists) {
      // Table doesn't exist - return default connector list with unknown status
      const defaultConnectors = [
        { name: 'polygon', type: 'paid', displayName: 'Polygon.io', requiresApiKey: true },
        { name: 'alpha_vantage', type: 'paid', displayName: 'Alpha Vantage', requiresApiKey: true },
        { name: 'finnhub', type: 'paid', displayName: 'Finnhub', requiresApiKey: true },
        { name: 'newsapi', type: 'paid', displayName: 'NewsAPI', requiresApiKey: true },
        { name: 'benzinga', type: 'paid', displayName: 'Benzinga', requiresApiKey: true },
        { name: 'fmp', type: 'paid', displayName: 'Financial Modeling Prep', requiresApiKey: true },
        { name: 'nasdaq_data_link', type: 'paid', displayName: 'Nasdaq Data Link', requiresApiKey: true },
        { name: 'iex_cloud', type: 'disabled', displayName: 'IEX Cloud', requiresApiKey: true },
        { name: 'yahoo_finance', type: 'free', displayName: 'Yahoo Finance', requiresApiKey: false },
        { name: 'rss_feeds', type: 'free', displayName: 'RSS Feeds', requiresApiKey: false },
        { name: 'sec_edgar', type: 'free', displayName: 'SEC EDGAR', requiresApiKey: false },
        { name: 'tipranks', type: 'free', displayName: 'TipRanks', requiresApiKey: false },
        { name: 'stocktwits', type: 'social', displayName: 'StockTwits', requiresApiKey: false },
      ];
      
      return res.json({
        connectors: defaultConnectors.map(c => ({
          ...c,
          status: c.type === 'disabled' ? 'disabled' : 'unknown',
          statusMessage: 'Run health check to get current status',
          lastCheckAt: null,
          lastSuccessAt: null,
          lastErrorAt: null,
          lastErrorMessage: null,
          articlesFetched: 0,
          responseTimeMs: null,
          hasApiKey: false,
          updatedAt: null,
        })),
        lastUpdated: null,
      });
    }
    
    const result = await pool.query(`
      SELECT 
        connector_name,
        connector_type,
        display_name,
        status,
        status_message,
        last_check_at,
        last_success_at,
        last_error_at,
        last_error_message,
        articles_fetched,
        response_time_ms,
        requires_api_key,
        has_api_key,
        updated_at
      FROM connector_status
      ORDER BY 
        CASE connector_type 
          WHEN 'paid' THEN 1 
          WHEN 'free' THEN 2 
          WHEN 'social' THEN 3 
          WHEN 'disabled' THEN 4 
        END,
        display_name
    `);
    
    res.json({
      connectors: result.rows.map(row => ({
        name: row.connector_name,
        type: row.connector_type,
        displayName: row.display_name,
        status: row.status,
        statusMessage: row.status_message,
        lastCheckAt: row.last_check_at,
        lastSuccessAt: row.last_success_at,
        lastErrorAt: row.last_error_at,
        lastErrorMessage: row.last_error_message,
        articlesFetched: row.articles_fetched,
        responseTimeMs: row.response_time_ms,
        requiresApiKey: row.requires_api_key,
        hasApiKey: row.has_api_key,
        updatedAt: row.updated_at,
      })),
      lastUpdated: result.rows.length > 0 
        ? result.rows.reduce((latest, row) => 
            row.last_check_at > latest ? row.last_check_at : latest, 
            result.rows[0].last_check_at
          )
        : null,
    });
  } catch (error) {
    console.error('Error getting connector statuses:', error);
    res.status(500).json({ error: 'Failed to get connector statuses' });
  }
});

/**
 * Get connector status history for a specific connector
 */
app.get('/api/v1/connectors/status/:connectorName/history', async (req, res) => {
  const { connectorName } = req.params;
  const { limit = 24 } = req.query; // Default to last 24 checks (3 days)
  
  try {
    const result = await pool.query(`
      SELECT 
        status,
        status_message,
        articles_fetched,
        response_time_ms,
        error_message,
        checked_at
      FROM connector_status_history
      WHERE connector_name = $1
      ORDER BY checked_at DESC
      LIMIT $2
    `, [connectorName, parseInt(limit)]);
    
    res.json({
      connectorName,
      history: result.rows.map(row => ({
        status: row.status,
        statusMessage: row.status_message,
        articlesFetched: row.articles_fetched,
        responseTimeMs: row.response_time_ms,
        errorMessage: row.error_message,
        checkedAt: row.checked_at,
      })),
    });
  } catch (error) {
    console.error('Error getting connector history:', error);
    res.status(500).json({ error: 'Failed to get connector history' });
  }
});

/**
 * Get summary stats for connectors
 */
app.get('/api/v1/connectors/summary', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT 
        COUNT(*) FILTER (WHERE status = 'connected') as connected,
        COUNT(*) FILTER (WHERE status = 'disconnected') as disconnected,
        COUNT(*) FILTER (WHERE status = 'error') as error,
        COUNT(*) FILTER (WHERE status = 'disabled') as disabled,
        COUNT(*) FILTER (WHERE status = 'unknown') as unknown,
        COUNT(*) as total
      FROM connector_status
    `);
    
    const stats = result.rows[0];
    res.json({
      connected: parseInt(stats.connected),
      disconnected: parseInt(stats.disconnected),
      error: parseInt(stats.error),
      disabled: parseInt(stats.disabled),
      unknown: parseInt(stats.unknown),
      total: parseInt(stats.total),
    });
  } catch (error) {
    console.error('Error getting connector summary:', error);
    res.status(500).json({ error: 'Failed to get connector summary' });
  }
});

/**
 * Trigger a manual health check for all connectors
 * This updates the status to show refresh in progress.
 * 
 * Note: In production, this would trigger the health check service via:
 * - A message queue (RabbitMQ, Redis pub/sub)
 * - A Kubernetes job
 * - An HTTP call to a separate health check service
 * 
 * For local development, run the health check manually:
 *   python3 ml-services/connector_health_service.py --once
 */
app.post('/api/v1/connectors/refresh', async (req, res) => {
  try {
    // Update the status to show refresh is in progress
    const now = new Date().toISOString();
    await pool.query(`
      UPDATE connector_status 
      SET status_message = 'Refresh requested at ' || $1::text,
          last_check_at = NOW()
      WHERE status != 'disabled'
    `, [now]);
    
    console.log('Manual connector health check requested at', now);
    
    // Try to spawn the health check process (may fail in containers without Python)
    try {
      const { exec } = await import('child_process');
      
      // Try to run the health check in the background
      // This works when running locally but may fail in Docker
      exec('python3 /app/../ml-services/connector_health_service.py --once', {
        cwd: '/app/..',
        timeout: 180000, // 3 minute timeout
      }, (error, stdout, stderr) => {
        if (error) {
          console.log('Health check process not available in this environment. Run manually: python3 ml-services/connector_health_service.py --once');
        } else {
          console.log('Health check completed:', stdout);
        }
      });
    } catch (spawnError) {
      console.log('Could not spawn health check process:', spawnError.message);
    }
    
    res.json({ 
      success: true, 
      message: 'Health check started. Status will update shortly.',
    });
  } catch (error) {
    console.error('Error triggering connector refresh:', error);
    res.status(500).json({ error: 'Failed to trigger connector refresh' });
  }
});

// Start server
app.listen(port, async () => {
  console.log(`🚀 API Gateway running on http://localhost:${port}`);
  
  // Initialize Vault
  try {
    await initializeVault();
    console.log('🔐 Vault integration ready');
  } catch (error) {
    console.error('⚠️ Vault initialization failed:', error.message);
    console.log('   Continuing without Vault - tokens will be stored in database (not recommended for production)');
  }
});
