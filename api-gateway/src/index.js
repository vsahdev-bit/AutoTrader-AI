import express from 'express';
import cors from 'cors';
import pg from 'pg';
import dotenv from 'dotenv';
import http from 'http';
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

// =============================================================================
// Jim Cramer Advice API Endpoints
// =============================================================================

/**
 * GET /api/jim-cramer/summary/latest
 * Get the latest daily summary of Jim Cramer's advice
 */
app.get('/api/jim-cramer/summary/latest', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT 
        id,
        summary_date,
        market_sentiment,
        market_sentiment_score,
        summary_title,
        summary_text,
        key_points,
        top_bullish_picks,
        top_bearish_picks,
        stocks_to_watch,
        sectors_bullish,
        sectors_bearish,
        total_articles_analyzed,
        total_stocks_mentioned,
        generated_at
      FROM jim_cramer_daily_summaries
      ORDER BY summary_date DESC
      LIMIT 1
    `);
    
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'No summary found' });
    }
    
    res.json(result.rows[0]);
  } catch (error) {
    console.error('Error fetching Jim Cramer summary:', error);
    res.status(500).json({ error: 'Failed to fetch summary' });
  }
});

/**
 * GET /api/jim-cramer/mentions/today
 * Get today's stock mentions from Jim Cramer articles
 */
app.get('/api/jim-cramer/mentions/today', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT 
        m.symbol,
        m.company_name,
        m.sentiment,
        m.sentiment_score,
        m.recommendation,
        m.reasoning,
        m.quote,
        a.title as article_title,
        a.article_url,
        a.published_at
      FROM jim_cramer_stock_mentions m
      JOIN jim_cramer_articles a ON m.article_id = a.id
      WHERE a.published_at >= CURRENT_DATE
      ORDER BY a.published_at DESC, m.sentiment_score DESC
      LIMIT 50
    `);
    
    res.json(result.rows);
  } catch (error) {
    console.error('Error fetching Jim Cramer mentions:', error);
    res.status(500).json({ error: 'Failed to fetch mentions' });
  }
});

/**
 * GET /api/jim-cramer/articles/recent
 * Get recent Jim Cramer articles
 */
app.get('/api/jim-cramer/articles/recent', async (req, res) => {
  const limit = Math.min(parseInt(req.query.limit) || 10, 50);
  
  try {
    const result = await pool.query(`
      SELECT 
        id,
        title,
        article_url,
        source_name,
        published_at,
        description
      FROM jim_cramer_articles
      ORDER BY published_at DESC
      LIMIT $1
    `, [limit]);
    
    res.json(result.rows);
  } catch (error) {
    console.error('Error fetching Jim Cramer articles:', error);
    res.status(500).json({ error: 'Failed to fetch articles' });
  }
});

/**
 * GET /api/jim-cramer/stock/:symbol
 * Get all mentions for a specific stock
 */
app.get('/api/jim-cramer/stock/:symbol', async (req, res) => {
  const symbol = req.params.symbol.toUpperCase();
  
  try {
    const result = await pool.query(`
      SELECT 
        m.symbol,
        m.company_name,
        m.sentiment,
        m.sentiment_score,
        m.recommendation,
        m.reasoning,
        m.quote,
        a.title as article_title,
        a.article_url,
        a.published_at
      FROM jim_cramer_stock_mentions m
      JOIN jim_cramer_articles a ON m.article_id = a.id
      WHERE m.symbol = $1
      ORDER BY a.published_at DESC
      LIMIT 20
    `, [symbol]);
    
    res.json(result.rows);
  } catch (error) {
    console.error('Error fetching stock mentions:', error);
    res.status(500).json({ error: 'Failed to fetch stock mentions' });
  }
});

// ============================================================================
// BIG CAP LOSERS ENDPOINTS
// ============================================================================

/**
 * GET /api/big-cap-losers/latest
 * Get the latest big cap losers (stocks with market cap > $1B)
 */
app.get('/api/big-cap-losers/latest', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT DISTINCT ON (symbol)
        id, symbol, company_name, current_price, price_change, percent_change,
        market_cap, market_cap_formatted, volume, trading_date, crawled_at
      FROM big_cap_losers
      WHERE market_cap >= 1000000000
      ORDER BY symbol, crawled_at DESC
    `);
    
    // Sort by percent_change ascending (worst performers first)
    const sorted = result.rows.sort((a, b) => a.percent_change - b.percent_change);
    res.json(sorted);
  } catch (error) {
    console.error('Error fetching big cap losers:', error);
    res.status(500).json({ error: 'Failed to fetch big cap losers' });
  }
});

/**
 * GET /api/big-cap-losers/over-10
 * Get big cap losers that have fallen more than 10%
 */
app.get('/api/big-cap-losers/over-10', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT DISTINCT ON (symbol)
        id, symbol, company_name, current_price, price_change, percent_change,
        market_cap, market_cap_formatted, volume, trading_date, crawled_at
      FROM big_cap_losers
      WHERE market_cap >= 1000000000
        AND percent_change <= -10.0
      ORDER BY symbol, crawled_at DESC
    `);
    
    const sorted = result.rows.sort((a, b) => a.percent_change - b.percent_change);
    res.json(sorted);
  } catch (error) {
    console.error('Error fetching big cap losers over 10%:', error);
    res.status(500).json({ error: 'Failed to fetch big cap losers' });
  }
});

/**
 * GET /api/big-cap-losers/today
 * Get today's big cap losers
 */
app.get('/api/big-cap-losers/today', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT 
        id, symbol, company_name, current_price, price_change, percent_change,
        market_cap, market_cap_formatted, volume, trading_date, crawled_at
      FROM big_cap_losers
      WHERE trading_date = CURRENT_DATE
        AND market_cap >= 1000000000
      ORDER BY percent_change ASC
    `);
    
    res.json(result.rows);
  } catch (error) {
    console.error('Error fetching today\'s big cap losers:', error);
    res.status(500).json({ error: 'Failed to fetch big cap losers' });
  }
});

/**
 * GET /api/big-cap-losers/summary
 * Get the daily summary of big cap losers
 */
app.get('/api/big-cap-losers/summary', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT *
      FROM big_cap_losers_daily_summary
      ORDER BY summary_date DESC
      LIMIT 1
    `);
    
    if (result.rows.length === 0) {
      return res.json(null);
    }
    
    res.json(result.rows[0]);
  } catch (error) {
    console.error('Error fetching big cap losers summary:', error);
    res.status(500).json({ error: 'Failed to fetch summary' });
  }
});

/**
 * GET /api/big-cap-losers/history/:symbol
 * Get historical data for a specific symbol
 */
app.get('/api/big-cap-losers/history/:symbol', async (req, res) => {
  const symbol = req.params.symbol.toUpperCase();
  
  try {
    const result = await pool.query(`
      SELECT 
        id, symbol, company_name, current_price, price_change, percent_change,
        market_cap, market_cap_formatted, volume, trading_date, crawled_at
      FROM big_cap_losers
      WHERE symbol = $1
      ORDER BY crawled_at DESC
      LIMIT 30
    `, [symbol]);
    
    res.json(result.rows);
  } catch (error) {
    console.error('Error fetching symbol history:', error);
    res.status(500).json({ error: 'Failed to fetch symbol history' });
  }
});

// ============================================================================
// CRAWLER SERVICE HEALTH CHECK ENDPOINTS
// ============================================================================

/**
 * GET /api/v1/crawler-services/status
 * Get status of all crawler services (Jim Cramer, Big Cap Losers)
 */
app.get('/api/v1/crawler-services/status', async (req, res) => {
  try {
    // Get Jim Cramer service status from crawl logs
    const jimCramerResult = await pool.query(`
      SELECT 
        'jim_cramer' as service_name,
        status,
        articles_found,
        articles_new,
        started_at as last_run_at,
        duration_seconds,
        error_message
      FROM jim_cramer_crawl_logs
      ORDER BY crawl_date DESC, started_at DESC
      LIMIT 1
    `);
    
    // Get Big Cap Losers service status from crawl logs
    const bigCapResult = await pool.query(`
      SELECT 
        'big_cap_losers' as service_name,
        status,
        total_losers_found,
        big_cap_losers_found,
        over_15_percent_found as over_threshold_found,
        started_at as last_run_at,
        duration_seconds,
        error_message
      FROM big_cap_losers_crawl_logs
      ORDER BY crawl_timestamp DESC
      LIMIT 1
    `);
    
    // Get health check settings for these services
    const settingsResult = await pool.query(`
      SELECT setting_key, enabled, updated_at 
      FROM health_check_settings
      WHERE setting_key IN ('jim_cramer_service', 'big_cap_losers_service')
    `);
    
    const settings = {};
    settingsResult.rows.forEach(row => {
      settings[row.setting_key] = { enabled: row.enabled, updatedAt: row.updated_at };
    });
    
    const jimCramer = jimCramerResult.rows[0] || null;
    const bigCapLosers = bigCapResult.rows[0] || null;
    
    res.json({
      jimCramerService: {
        status: jimCramer ? (jimCramer.status === 'success' ? 'connected' : 'error') : 'unknown',
        lastRunAt: jimCramer?.last_run_at || null,
        articlesFound: jimCramer?.articles_found || 0,
        articlesNew: jimCramer?.articles_new || 0,
        durationSeconds: jimCramer?.duration_seconds || null,
        errorMessage: jimCramer?.error_message || null,
        enabled: settings['jim_cramer_service']?.enabled ?? true
      },
      bigCapLosersService: {
        status: bigCapLosers ? (bigCapLosers.status === 'success' ? 'connected' : 'error') : 'unknown',
        lastRunAt: bigCapLosers?.last_run_at || null,
        totalLosersFound: bigCapLosers?.total_losers_found || 0,
        bigCapLosersFound: bigCapLosers?.big_cap_losers_found || 0,
        overThresholdFound: bigCapLosers?.over_threshold_found || 0,
        durationSeconds: bigCapLosers?.duration_seconds || null,
        errorMessage: bigCapLosers?.error_message || null,
        enabled: settings['big_cap_losers_service']?.enabled ?? true
      }
    });
  } catch (error) {
    console.error('Error fetching crawler services status:', error);
    res.status(500).json({ error: 'Failed to fetch crawler services status' });
  }
});

/**
 * PUT /api/v1/crawler-services/settings/:service
 * Update health check enabled setting for a crawler service
 */
app.put('/api/v1/crawler-services/settings/:service', async (req, res) => {
  const { service } = req.params;
  const { enabled } = req.body;
  
  const validServices = ['jim_cramer_service', 'big_cap_losers_service'];
  if (!validServices.includes(service)) {
    return res.status(400).json({ error: 'Invalid service name' });
  }
  
  try {
    const result = await pool.query(`
      INSERT INTO health_check_settings (setting_key, enabled, updated_at)
      VALUES ($1, $2, NOW())
      ON CONFLICT (setting_key) DO UPDATE 
      SET enabled = $2, updated_at = NOW()
      RETURNING setting_key, enabled, updated_at
    `, [service, enabled]);
    
    res.json({
      success: true,
      setting: {
        key: result.rows[0].setting_key,
        enabled: result.rows[0].enabled,
        updatedAt: result.rows[0].updated_at
      }
    });
  } catch (error) {
    console.error('Error updating crawler service setting:', error);
    res.status(500).json({ error: 'Failed to update crawler service setting' });
  }
});

/**
 * POST /api/v1/crawler-services/jim-cramer/run
 * Trigger a manual run of the Jim Cramer service
 */
app.post('/api/v1/crawler-services/jim-cramer/run', async (req, res) => {
  try {
    // We'll use Docker exec to run the service
    const { exec } = require('child_process');
    
    // Run the Jim Cramer service once
    exec('docker exec autotrader-jim-cramer python service.py --once 2>&1 || echo "Service triggered"', 
      { timeout: 5000 },
      (error, stdout, stderr) => {
        if (error && !stdout.includes('triggered')) {
          console.log('Jim Cramer service trigger note:', error.message);
        }
      }
    );
    
    res.json({
      success: true,
      message: 'Jim Cramer service run triggered. Check status in a few minutes.'
    });
  } catch (error) {
    console.error('Error triggering Jim Cramer service:', error);
    res.status(500).json({ error: 'Failed to trigger Jim Cramer service' });
  }
});

/**
 * POST /api/v1/crawler-services/big-cap-losers/run
 * Trigger a manual run of the Big Cap Losers service
 */
app.post('/api/v1/crawler-services/big-cap-losers/run', async (req, res) => {
  try {
    // We'll use Docker exec to run the service
    const { exec } = require('child_process');
    
    // Run the Big Cap Losers service once
    exec('docker exec autotrader-big-cap-losers python service.py --once 2>&1 || echo "Service triggered"',
      { timeout: 5000 },
      (error, stdout, stderr) => {
        if (error && !stdout.includes('triggered')) {
          console.log('Big Cap Losers service trigger note:', error.message);
        }
      }
    );
    
    res.json({
      success: true,
      message: 'Big Cap Losers service run triggered. Check status in a few minutes.'
    });
  } catch (error) {
    console.error('Error triggering Big Cap Losers service:', error);
    res.status(500).json({ error: 'Failed to trigger Big Cap Losers service' });
  }
});

/**
 * GET /api/big-cap-losers/with-recommendations
 * Get big cap losers with their AI recommendations
 */
app.get('/api/big-cap-losers/with-recommendations', async (req, res) => {
  try {
    // Only show stocks from the latest crawl batch (within 5 minutes of the most recent crawl)
    const result = await pool.query(`
      WITH latest_crawl AS (
        SELECT MAX(crawled_at) as max_crawl_time
        FROM big_cap_losers
      )
      SELECT DISTINCT ON (bcl.symbol)
        bcl.id as loser_id,
        bcl.symbol,
        bcl.company_name,
        bcl.current_price,
        bcl.price_change,
        bcl.percent_change,
        bcl.market_cap,
        bcl.market_cap_formatted,
        bcl.volume,
        bcl.trading_date,
        bcl.crawled_at,
        rec.id as recommendation_id,
        rec.action,
        rec.score,
        rec.normalized_score,
        rec.confidence,
        rec.market_regime,
        rec.regime_confidence,
        rec.news_score,
        rec.technical_score,
        rec.explanation,
        rec.generated_at as recommendation_generated_at
      FROM big_cap_losers bcl
      CROSS JOIN latest_crawl lc
      LEFT JOIN LATERAL (
        SELECT *
        FROM big_cap_losers_recommendations r
        WHERE r.symbol = bcl.symbol
        ORDER BY r.generated_at DESC
        LIMIT 1
      ) rec ON true
      WHERE bcl.market_cap >= 1000000000
        AND bcl.crawled_at >= lc.max_crawl_time - INTERVAL '5 minutes'
      ORDER BY bcl.symbol, bcl.crawled_at DESC
    `);
    
    const sorted = result.rows.sort((a, b) => a.percent_change - b.percent_change);
    res.json(sorted);
  } catch (error) {
    console.error('Error fetching big cap losers with recommendations:', error);
    res.status(500).json({ error: 'Failed to fetch data' });
  }
});

/**
 * POST /api/big-cap-losers/generate-recommendations
 * Generate AI recommendations for all current big cap losers
 * Fetches from the existing stock_recommendations table if available
 */
app.post('/api/big-cap-losers/generate-recommendations', async (req, res) => {
  
  try {
    // Get all current big cap losers
    const losersResult = await pool.query(`
      SELECT DISTINCT ON (symbol)
        id, symbol, current_price, percent_change
      FROM big_cap_losers
      WHERE market_cap >= 1000000000
      ORDER BY symbol, crawled_at DESC
    `);
    
    const symbols = losersResult.rows.map(r => r.symbol);
    
    if (symbols.length === 0) {
      return res.json({ success: true, message: 'No big cap losers to analyze', generated: 0 });
    }
    
    console.log(`Looking for recommendations for ${symbols.length} big cap losers: ${symbols.join(', ')}`);
    
    // First, try to get existing recommendations from the main stock_recommendations table
    const existingRecs = await pool.query(`
      SELECT DISTINCT ON (symbol)
        symbol, action, score, normalized_score, confidence,
        explanation, data_sources_used, generated_at,
        price_at_recommendation
      FROM stock_recommendations
      WHERE symbol = ANY($1)
      ORDER BY symbol, generated_at DESC
    `, [symbols]);
    
    let saved = 0;
    
    // Copy relevant recommendations to big_cap_losers_recommendations
    for (const rec of existingRecs.rows) {
      try {
        const loser = losersResult.rows.find(l => l.symbol === rec.symbol);
        
        // Check if we already have this recommendation
        const existing = await pool.query(`
          SELECT id FROM big_cap_losers_recommendations
          WHERE symbol = $1 AND generated_at = $2
        `, [rec.symbol, rec.generated_at]);
        
        if (existing.rows.length === 0) {
          // Parse explanation if it's a string
          let explanation = rec.explanation;
          if (typeof explanation === 'string') {
            try { explanation = JSON.parse(explanation); } catch(e) { explanation = {}; }
          }
          
          await pool.query(`
            INSERT INTO big_cap_losers_recommendations (
              big_cap_loser_id, symbol, action, score, normalized_score, confidence,
              price_at_recommendation, explanation, data_sources_used, generated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
          `, [
            loser?.id || null,
            rec.symbol,
            rec.action,
            rec.score || 0,
            rec.normalized_score || 0.5,
            rec.confidence || 0.5,
            rec.price_at_recommendation || loser?.current_price,
            JSON.stringify(explanation || {}),
            rec.data_sources_used || [],
            rec.generated_at
          ]);
          saved++;
        }
      } catch (saveErr) {
        console.error(`Error saving recommendation for ${rec.symbol}:`, saveErr.message);
      }
    }
    
    // For symbols without recommendations, create placeholder recommendations with regime data
    const symbolsWithRecs = new Set(existingRecs.rows.map(r => r.symbol));
    const symbolsWithoutRecs = symbols.filter(s => !symbolsWithRecs.has(s));
    
    // Helper function to fetch regime data
    const fetchRegime = async (symbol) => {
      return new Promise((resolve) => {
        const req = http.request({
          hostname: 'recommendation-engine',
          port: 8000,
          path: `/regime/${symbol}`,
          method: 'GET',
          timeout: 10000
        }, (res) => {
          let data = '';
          res.on('data', chunk => data += chunk);
          res.on('end', () => {
            try {
              resolve(JSON.parse(data));
            } catch (e) {
              resolve(null);
            }
          });
        });
        req.on('error', () => resolve(null));
        req.on('timeout', () => { req.destroy(); resolve(null); });
        req.end();
      });
    };
    
    for (const symbol of symbolsWithoutRecs) {
      try {
        const loser = losersResult.rows.find(l => l.symbol === symbol);
        const percentDrop = parseFloat(loser?.percent_change || 0);
        
        // Fetch market regime for this symbol
        let market_regime = null;
        let regime_confidence = null;
        
        try {
          const regimeData = await fetchRegime(symbol);
          if (regimeData && regimeData.regime) {
            market_regime = regimeData.regime.label || regimeData.regime.volatility;
            // Use confidence if available, otherwise use risk_score, or 1 - risk_score for inverse
            regime_confidence = regimeData.regime.confidence ?? regimeData.regime.risk_score ?? null;
          }
        } catch (regimeErr) {
          console.log(`Could not fetch regime for ${symbol}: ${regimeErr.message}`);
        }
        
        // Calculate a meaningful score based on multiple factors
        // Factors: drop magnitude, market cap tier, regime risk
        const dropMagnitude = Math.abs(percentDrop);
        const marketCap = parseFloat(loser?.market_cap || 0);
        
        // Base score from drop magnitude (contrarian: bigger drop = potentially better opportunity)
        // Maps -5% to -25%+ drop to 0.4-0.8 score range
        let dropScore = Math.min(0.8, Math.max(0.4, 0.4 + (dropMagnitude - 5) * 0.02));
        
        // Market cap factor: larger companies are generally safer (slight boost)
        let capBoost = 0;
        if (marketCap >= 100000000000) capBoost = 0.05; // >$100B
        else if (marketCap >= 50000000000) capBoost = 0.03; // >$50B
        else if (marketCap >= 10000000000) capBoost = 0.01; // >$10B
        
        // Regime adjustment: if we have regime data, adjust based on trend/volatility
        let regimeAdjust = 0;
        if (regime_confidence !== null) {
          // Lower risk_score is better, so invert it
          regimeAdjust = (0.5 - (regime_confidence || 0.5)) * 0.1;
        }
        
        // Calculate final normalized score (0-1 range)
        let normalized_score = Math.min(0.95, Math.max(0.3, dropScore + capBoost + regimeAdjust));
        
        // Use regime confidence if available, otherwise calculate based on data availability
        let confidence = regime_confidence ?? (Math.abs(percentDrop) > 15 ? 0.6 : Math.abs(percentDrop) > 10 ? 0.5 : 0.4);
        
        // Determine action based on normalized score
        let action = 'HOLD';
        if (normalized_score >= 0.65) {
          action = 'BUY';
        } else if (normalized_score <= 0.35) {
          action = 'SELL';
        }
        
        await pool.query(`
          INSERT INTO big_cap_losers_recommendations (
            big_cap_loser_id, symbol, action, score, normalized_score, confidence,
            market_regime, regime_confidence,
            price_at_recommendation, explanation, data_sources_used, generated_at
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
        `, [
          loser?.id || null,
          symbol,
          action,
          normalized_score - 0.5, // Convert to -0.5 to 0.5 scale
          normalized_score,
          confidence,
          market_regime,
          regime_confidence,
          loser?.current_price,
          JSON.stringify({
            summary: `Stock has dropped ${Math.abs(percentDrop).toFixed(1)}% today. This significant move warrants careful analysis before taking action.`,
            reasoning: percentDrop <= -15 
              ? 'Large single-day drops can indicate panic selling and potential oversold conditions, presenting possible buying opportunities for contrarian investors.'
              : 'Moderate drop detected. Recommend monitoring for further developments before taking action.',
            key_factors: [
              `${Math.abs(percentDrop).toFixed(1)}% daily decline`,
              `Market cap: ${loser?.market_cap_formatted || 'Unknown'}`,
              market_regime ? `Market regime: ${market_regime}` : 'Recommendation pending full analysis'
            ],
            risk_factors: [
              'Large price movements may indicate fundamental issues',
              'Further downside possible',
              'Limited real-time data available'
            ]
          }),
          ['price_data', 'regime_data'],
        ]);
        saved++;
      } catch (saveErr) {
        console.error(`Error creating placeholder recommendation for ${symbol}:`, saveErr.message);
      }
    }
    
    res.json({
      success: true,
      message: `Generated recommendations for ${saved} stocks`,
      generated: saved,
      fromExisting: existingRecs.rows.length,
      newlyGenerated: symbolsWithoutRecs.length,
      symbols: symbols
    });
    
  } catch (error) {
    console.error('Error generating recommendations for big cap losers:', error);
    res.status(500).json({ error: 'Failed to generate recommendations' });
  }
});

/**
 * GET /api/big-cap-losers/recommendation/:symbol
 * Get recommendation details for a specific big cap loser
 */
app.get('/api/big-cap-losers/recommendation/:symbol', async (req, res) => {
  const symbol = req.params.symbol.toUpperCase();
  
  try {
    const result = await pool.query(`
      SELECT 
        r.*,
        bcl.company_name,
        bcl.current_price,
        bcl.percent_change,
        bcl.market_cap_formatted
      FROM big_cap_losers_recommendations r
      JOIN big_cap_losers bcl ON bcl.symbol = r.symbol
      WHERE r.symbol = $1
      ORDER BY r.generated_at DESC
      LIMIT 1
    `, [symbol]);
    
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'No recommendation found for this symbol' });
    }
    
    res.json(result.rows[0]);
  } catch (error) {
    console.error('Error fetching recommendation:', error);
    res.status(500).json({ error: 'Failed to fetch recommendation' });
  }
});

/**
 * POST /api/big-cap-losers/refresh
 * Trigger a fresh crawl and return the updated results
 */
app.post('/api/big-cap-losers/refresh', async (req, res) => {
  try {
    console.log('Starting Big Cap Losers refresh...');
    
    // Try to trigger the crawler service via HTTP
    // Use host.docker.internal when running in Docker to reach services on host machine
    const crawlerServiceUrl = process.env.BIG_CAP_LOSERS_SERVICE_URL || 'http://host.docker.internal:8001';
    
    let crawlerStats = null;
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minute timeout
      
      const crawlerResponse = await fetch(`${crawlerServiceUrl}/refresh`, {
        method: 'POST',
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (crawlerResponse.ok) {
        const crawlerData = await crawlerResponse.json();
        console.log('Crawler service response:', crawlerData);
        // Capture stats from crawler service
        crawlerStats = crawlerData.stats || null;
      } else {
        console.log('Crawler service returned non-OK status:', crawlerResponse.status);
      }
    } catch (fetchError) {
      // If the crawler service is not running, fall back to just fetching existing data
      console.log('Could not reach crawler service, fetching existing data:', fetchError.message);
    }
    
    // Wait a moment for DB to update
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Fetch the updated results from database
    const result = await pool.query(`
      SELECT DISTINCT ON (symbol)
        id, symbol, company_name, current_price, price_change, percent_change,
        market_cap, market_cap_formatted, volume, trading_date, crawled_at
      FROM big_cap_losers
      WHERE market_cap >= 1000000000
      ORDER BY symbol, crawled_at DESC
    `);
    
    const over10Result = await pool.query(`
      SELECT DISTINCT ON (symbol)
        id, symbol, company_name, current_price, price_change, percent_change,
        market_cap, market_cap_formatted, volume, trading_date, crawled_at
      FROM big_cap_losers
      WHERE market_cap >= 1000000000
        AND percent_change <= -10.0
      ORDER BY symbol, crawled_at DESC
    `);
    
    const allLosers = result.rows.sort((a, b) => a.percent_change - b.percent_change);
    const over10Losers = over10Result.rows.sort((a, b) => a.percent_change - b.percent_change);
    
    res.json({
      success: true,
      message: 'Data refreshed successfully',
      stats: crawlerStats,  // Pass through crawler stats
      allLosers,
      over10Losers,
      refreshedAt: new Date().toISOString()
    });
  } catch (error) {
    console.error('Error refreshing Big Cap Losers:', error);
    res.status(500).json({ error: 'Failed to refresh data' });
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
