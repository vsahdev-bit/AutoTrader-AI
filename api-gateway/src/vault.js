import vault from 'node-vault';
import crypto from 'crypto';

// Vault configuration
const VAULT_ADDR = process.env.VAULT_ADDR || 'http://localhost:8200';
const VAULT_TOKEN = process.env.VAULT_TOKEN || 'dev-root-token';
const SECRETS_PATH = 'secret/data/autotrader'; // KV v2 secrets engine

// Initialize Vault client
const vaultClient = vault({
  apiVersion: 'v1',
  endpoint: VAULT_ADDR,
  token: VAULT_TOKEN,
});

// Initialize the secrets engine (run once on startup)
export async function initializeVault() {
  try {
    // Check if KV v2 secrets engine is enabled
    const mounts = await vaultClient.mounts();
    
    if (!mounts.data['secret/']) {
      // Enable KV v2 secrets engine
      await vaultClient.mount({
        mount_point: 'secret',
        type: 'kv',
        options: { version: '2' },
      });
      console.log('✅ Vault KV v2 secrets engine enabled');
    }
    
    console.log('✅ Vault initialized successfully');
    return true;
  } catch (error) {
    // If already exists, that's fine
    if (error.message?.includes('path is already in use')) {
      console.log('✅ Vault KV secrets engine already enabled');
      return true;
    }
    console.error('⚠️ Vault initialization warning:', error.message);
    // Continue anyway - might be using dev mode
    return true;
  }
}

/**
 * Store a Plaid access token securely in Vault
 * @param {string} userId - User ID
 * @param {string} itemId - Plaid Item ID
 * @param {string} accessToken - Plaid access token to store
 * @param {object} metadata - Additional metadata (institution info, etc.)
 */
export async function storePlaidToken(userId, itemId, accessToken, metadata = {}) {
  const secretPath = `${SECRETS_PATH}/plaid/${userId}/${itemId}`;
  
  try {
    await vaultClient.write(secretPath, {
      data: {
        access_token: accessToken,
        user_id: userId,
        item_id: itemId,
        institution_id: metadata.institutionId,
        institution_name: metadata.institutionName,
        created_at: new Date().toISOString(),
        ...metadata,
      },
    });
    
    console.log(`✅ Stored Plaid token in Vault for user ${userId}, item ${itemId}`);
    return true;
  } catch (error) {
    console.error('Error storing token in Vault:', error.message);
    throw new Error('Failed to store token securely');
  }
}

/**
 * Retrieve a Plaid access token from Vault
 * @param {string} userId - User ID
 * @param {string} itemId - Plaid Item ID
 * @returns {object} Token data including access_token
 */
export async function getPlaidToken(userId, itemId) {
  const secretPath = `${SECRETS_PATH}/plaid/${userId}/${itemId}`;
  
  try {
    const result = await vaultClient.read(secretPath);
    return result.data.data;
  } catch (error) {
    if (error.response?.statusCode === 404) {
      return null;
    }
    console.error('Error retrieving token from Vault:', error.message);
    throw new Error('Failed to retrieve token');
  }
}

/**
 * Delete a Plaid access token from Vault
 * @param {string} userId - User ID
 * @param {string} itemId - Plaid Item ID
 */
export async function deletePlaidToken(userId, itemId) {
  const secretPath = `secret/metadata/autotrader/plaid/${userId}/${itemId}`;
  
  try {
    await vaultClient.delete(secretPath);
    console.log(`✅ Deleted Plaid token from Vault for user ${userId}, item ${itemId}`);
    return true;
  } catch (error) {
    console.error('Error deleting token from Vault:', error.message);
    // Don't throw - deletion failure shouldn't block disconnect
    return false;
  }
}

/**
 * List all Plaid tokens for a user
 * @param {string} userId - User ID
 * @returns {string[]} List of item IDs
 */
export async function listUserPlaidTokens(userId) {
  const listPath = `secret/metadata/autotrader/plaid/${userId}`;
  
  try {
    const result = await vaultClient.list(listPath);
    return result.data.keys || [];
  } catch (error) {
    if (error.response?.statusCode === 404) {
      return [];
    }
    console.error('Error listing tokens from Vault:', error.message);
    return [];
  }
}

/**
 * Store generic secret (for Plaid API credentials, etc.)
 * @param {string} key - Secret key name
 * @param {object} value - Secret value(s)
 */
export async function storeSecret(key, value) {
  const secretPath = `${SECRETS_PATH}/config/${key}`;
  
  try {
    await vaultClient.write(secretPath, { data: value });
    return true;
  } catch (error) {
    console.error('Error storing secret in Vault:', error.message);
    throw error;
  }
}

/**
 * Retrieve generic secret
 * @param {string} key - Secret key name
 * @returns {object} Secret value(s)
 */
export async function getSecret(key) {
  const secretPath = `${SECRETS_PATH}/config/${key}`;
  
  try {
    const result = await vaultClient.read(secretPath);
    return result.data.data;
  } catch (error) {
    if (error.response?.statusCode === 404) {
      return null;
    }
    console.error('Error retrieving secret from Vault:', error.message);
    return null;
  }
}

// ============== TRADE AUTHORIZATION TOKENS ==============

/**
 * Generate a cryptographically secure token
 */
function generateSecureToken() {
  return crypto.randomBytes(32).toString('hex');
}

/**
 * Hash a value using SHA256
 */
export function hashValue(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

/**
 * Create a short-lived trade authorization token
 * @param {string} userId - User ID
 * @param {string} tradeAuthId - Trade authorization ID from database
 * @param {object} tradeDetails - Trade details (symbol, action, quantity, etc.)
 * @param {number} ttlSeconds - Time to live in seconds (default 5 minutes)
 * @returns {object} { token, expiresAt }
 */
export async function createTradeAuthToken(userId, tradeAuthId, tradeDetails, ttlSeconds = 300) {
  const token = generateSecureToken();
  const secretPath = `${SECRETS_PATH}/trade-auth/${userId}/${tradeAuthId}`;
  const expiresAt = new Date(Date.now() + ttlSeconds * 1000);
  
  try {
    await vaultClient.write(secretPath, {
      data: {
        token,
        user_id: userId,
        trade_auth_id: tradeAuthId,
        trade_details: tradeDetails,
        created_at: new Date().toISOString(),
        expires_at: expiresAt.toISOString(),
        ttl_seconds: ttlSeconds,
      },
    });
    
    console.log(`✅ Created trade auth token for user ${userId}, trade ${tradeAuthId} (TTL: ${ttlSeconds}s)`);
    
    return {
      token,
      expiresAt,
      ttlSeconds,
    };
  } catch (error) {
    console.error('Error creating trade auth token in Vault:', error.message);
    throw new Error('Failed to create trade authorization token');
  }
}

/**
 * Validate a trade authorization token
 * @param {string} userId - User ID
 * @param {string} tradeAuthId - Trade authorization ID
 * @param {string} token - Token to validate
 * @returns {object|null} Trade details if valid, null if invalid/expired
 */
export async function validateTradeAuthToken(userId, tradeAuthId, token) {
  const secretPath = `${SECRETS_PATH}/trade-auth/${userId}/${tradeAuthId}`;
  
  try {
    const result = await vaultClient.read(secretPath);
    const data = result.data.data;
    
    // Check if token matches
    if (data.token !== token) {
      console.log('Trade auth token mismatch');
      return null;
    }
    
    // Check if expired
    const expiresAt = new Date(data.expires_at);
    if (expiresAt < new Date()) {
      console.log('Trade auth token expired');
      // Delete the expired token
      await deleteTradeAuthToken(userId, tradeAuthId);
      return null;
    }
    
    return {
      valid: true,
      tradeDetails: data.trade_details,
      expiresAt: data.expires_at,
      createdAt: data.created_at,
    };
  } catch (error) {
    if (error.response?.statusCode === 404) {
      return null;
    }
    console.error('Error validating trade auth token:', error.message);
    return null;
  }
}

/**
 * Consume (use and delete) a trade authorization token
 * This is called when the trade is executed
 * @param {string} userId - User ID
 * @param {string} tradeAuthId - Trade authorization ID
 * @param {string} token - Token to consume
 * @returns {object|null} Trade details if valid, null if invalid
 */
export async function consumeTradeAuthToken(userId, tradeAuthId, token) {
  // First validate the token
  const validation = await validateTradeAuthToken(userId, tradeAuthId, token);
  
  if (!validation) {
    return null;
  }
  
  // Delete the token (it can only be used once)
  await deleteTradeAuthToken(userId, tradeAuthId);
  
  console.log(`✅ Consumed trade auth token for user ${userId}, trade ${tradeAuthId}`);
  
  return validation;
}

/**
 * Delete a trade authorization token
 * @param {string} userId - User ID
 * @param {string} tradeAuthId - Trade authorization ID
 */
export async function deleteTradeAuthToken(userId, tradeAuthId) {
  const secretPath = `secret/metadata/autotrader/trade-auth/${userId}/${tradeAuthId}`;
  
  try {
    await vaultClient.delete(secretPath);
    console.log(`✅ Deleted trade auth token for user ${userId}, trade ${tradeAuthId}`);
    return true;
  } catch (error) {
    // Ignore 404 errors
    if (error.response?.statusCode !== 404) {
      console.error('Error deleting trade auth token:', error.message);
    }
    return false;
  }
}

/**
 * Clean up expired trade auth tokens for a user
 * @param {string} userId - User ID
 */
export async function cleanupExpiredTradeAuthTokens(userId) {
  const listPath = `secret/metadata/autotrader/trade-auth/${userId}`;
  
  try {
    const result = await vaultClient.list(listPath);
    const tradeAuthIds = result.data.keys || [];
    
    let cleanedCount = 0;
    for (const tradeAuthId of tradeAuthIds) {
      const secretPath = `${SECRETS_PATH}/trade-auth/${userId}/${tradeAuthId}`;
      try {
        const secret = await vaultClient.read(secretPath);
        const expiresAt = new Date(secret.data.data.expires_at);
        if (expiresAt < new Date()) {
          await deleteTradeAuthToken(userId, tradeAuthId.replace('/', ''));
          cleanedCount++;
        }
      } catch (e) {
        // Ignore read errors
      }
    }
    
    return cleanedCount;
  } catch (error) {
    if (error.response?.statusCode === 404) {
      return 0;
    }
    console.error('Error cleaning up trade auth tokens:', error.message);
    return 0;
  }
}

// Health check
export async function checkVaultHealth() {
  try {
    const health = await vaultClient.health();
    return {
      healthy: !health.sealed,
      initialized: health.initialized,
      sealed: health.sealed,
      version: health.version,
    };
  } catch (error) {
    return {
      healthy: false,
      error: error.message,
    };
  }
}

export default {
  initializeVault,
  storePlaidToken,
  getPlaidToken,
  deletePlaidToken,
  listUserPlaidTokens,
  storeSecret,
  getSecret,
  createTradeAuthToken,
  validateTradeAuthToken,
  consumeTradeAuthToken,
  deleteTradeAuthToken,
  cleanupExpiredTradeAuthTokens,
  checkVaultHealth,
};
