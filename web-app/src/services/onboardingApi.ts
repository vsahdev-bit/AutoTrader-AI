const API_BASE = 'http://localhost:3001/api';

export interface User {
  id: string;
  email: string;
  auth_provider: string;
}

export type OnboardingStatusType = 'not_started' | 'in_progress' | 'completed';

export interface OnboardingStatus {
  user_id: string;
  status: OnboardingStatusType;
  current_step: number;
  completed_steps: number[];
}

export interface UserProfile {
  display_name?: string;
  phone?: string;
  country?: string;
  timezone?: string;
}

export interface TradingPreferences {
  experience_level?: 'beginner' | 'intermediate' | 'advanced' | 'expert';
  investment_goals?: string[];
  risk_tolerance?: 'conservative' | 'moderate' | 'aggressive';
  trading_frequency?: 'daily' | 'weekly' | 'monthly' | 'occasional';
  initial_investment_range?: string;
}

export interface WatchlistStock {
  id: string;
  symbol: string;
  company_name: string;
  exchange: string;
}

export interface BrokerageConnection {
  id: string;
  institution_id: string;
  institution_name: string;
  status: 'active' | 'disconnected' | 'error';
  last_synced_at: string | null;
  created_at: string;
}

export interface StockSearchResult {
  symbol: string;
  name: string;
  exchange: string;
  type: string;
}

// Authenticate user and get/create their account
export async function authenticateUser(userData: {
  email: string;
  name: string;
  picture: string;
  googleId: string;
}): Promise<{ user: User; onboarding: OnboardingStatus }> {
  const response = await fetch(`${API_BASE}/users/auth`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(userData),
  });
  return response.json();
}

// Get onboarding data
export async function getOnboardingData(userId: string): Promise<{
  onboarding: OnboardingStatus;
  profile: UserProfile;
  preferences: TradingPreferences;
  watchlist: WatchlistStock[];
  brokerageConnections: BrokerageConnection[];
}> {
  const response = await fetch(`${API_BASE}/onboarding/${userId}`);
  return response.json();
}

// Update onboarding status
export async function updateOnboardingStatus(
  userId: string,
  data: { status: string; currentStep: number; completedSteps: number[] }
): Promise<OnboardingStatus> {
  const response = await fetch(`${API_BASE}/onboarding/${userId}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return response.json();
}

// Update profile
export async function updateProfile(userId: string, profile: UserProfile): Promise<UserProfile> {
  const response = await fetch(`${API_BASE}/onboarding/${userId}/profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      displayName: profile.display_name,
      phone: profile.phone,
      country: profile.country,
      timezone: profile.timezone,
    }),
  });
  return response.json();
}

// Update trading preferences
export async function updatePreferences(
  userId: string,
  preferences: TradingPreferences
): Promise<TradingPreferences> {
  const response = await fetch(`${API_BASE}/onboarding/${userId}/preferences`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      experienceLevel: preferences.experience_level,
      investmentGoals: preferences.investment_goals,
      riskTolerance: preferences.risk_tolerance,
      tradingFrequency: preferences.trading_frequency,
      initialInvestmentRange: preferences.initial_investment_range,
    }),
  });
  return response.json();
}

// Add stock to watchlist
export async function addToWatchlist(
  userId: string,
  stock: { symbol: string; companyName: string; exchange: string }
): Promise<WatchlistStock> {
  const response = await fetch(`${API_BASE}/onboarding/${userId}/watchlist`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(stock),
  });
  return response.json();
}

// Remove stock from watchlist
export async function removeFromWatchlist(userId: string, symbol: string): Promise<void> {
  await fetch(`${API_BASE}/onboarding/${userId}/watchlist/${symbol}`, {
    method: 'DELETE',
  });
}

// Search stocks
export async function searchStocks(query: string): Promise<StockSearchResult[]> {
  if (!query || query.length < 1) return [];
  const response = await fetch(`${API_BASE}/stocks/search?q=${encodeURIComponent(query)}`);
  return response.json();
}

// Complete onboarding
export async function completeOnboarding(userId: string): Promise<OnboardingStatus> {
  const response = await fetch(`${API_BASE}/onboarding/${userId}/complete`, {
    method: 'POST',
  });
  return response.json();
}

// ============== BROKERAGE / PLAID API ==============

// Create Plaid Link token
export async function createPlaidLinkToken(userId: string): Promise<{
  linkToken: string | null;
  sandbox?: boolean;
  message?: string;
}> {
  const response = await fetch(`${API_BASE}/plaid/create-link-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ userId }),
  });
  return response.json();
}

// Exchange public token for access token
export async function exchangePlaidToken(data: {
  userId: string;
  publicToken: string;
  institutionId?: string;
  institutionName?: string;
}): Promise<{
  success: boolean;
  sandbox?: boolean;
  connection?: BrokerageConnection;
}> {
  const response = await fetch(`${API_BASE}/plaid/exchange-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return response.json();
}

// Get brokerage connections
export async function getBrokerageConnections(userId: string): Promise<{
  connections: BrokerageConnection[];
  accounts: Array<{
    id: string;
    account_name: string;
    account_type: string;
    account_subtype: string;
    mask: string;
  }>;
}> {
  const response = await fetch(`${API_BASE}/brokerage/${userId}/connections`);
  return response.json();
}

// Disconnect brokerage
export async function disconnectBrokerage(userId: string, connectionId: string): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE}/brokerage/${userId}/connections/${connectionId}`, {
    method: 'DELETE',
  });
  return response.json();
}

// ============== TRADE AUTHORIZATION API ==============

export interface TradeDetails {
  symbol: string;
  action: 'BUY' | 'SELL';
  quantity: number;
  orderType?: 'market' | 'limit' | 'stop' | 'stop_limit';
  limitPrice?: number;
  brokerageConnectionId: string;
  institutionName?: string;
}

export interface TradeAuthorization {
  id: string;
  symbol: string;
  action: 'BUY' | 'SELL';
  quantity: number;
  orderType: string;
  limitPrice: number | null;
  status: 'pending' | 'confirmed' | 'executed' | 'expired' | 'cancelled';
  executedPrice: number | null;
  brokerOrderId: string | null;
  institutionName: string;
  createdAt: string;
  executedAt: string | null;
}

export interface TradeAuthResponse {
  success: boolean;
  tradeAuthId: string;
  token: string;
  expiresAt: string;
  ttlSeconds: number;
  tradeDetails: TradeDetails;
  message: string;
}

export interface TradeExecutionResponse {
  success: boolean;
  tradeAuthId: string;
  status: string;
  execution: {
    symbol: string;
    action: string;
    quantity: number;
    price: number;
    total: string;
    brokerOrderId: string;
    executedAt: string;
  };
  message: string;
}

// Create a trade authorization (step 1: initiate trade)
export async function createTradeAuthorization(
  userId: string,
  trade: TradeDetails
): Promise<TradeAuthResponse> {
  const response = await fetch(`${API_BASE}/trade/authorize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      userId,
      brokerageConnectionId: trade.brokerageConnectionId,
      symbol: trade.symbol,
      action: trade.action,
      quantity: trade.quantity,
      orderType: trade.orderType || 'market',
      limitPrice: trade.limitPrice,
    }),
  });
  return response.json();
}

// Execute a trade (step 2: confirm and execute)
export async function executeTrade(
  userId: string,
  tradeAuthId: string,
  token: string,
  pin?: string
): Promise<TradeExecutionResponse> {
  const response = await fetch(`${API_BASE}/trade/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ userId, tradeAuthId, token, pin }),
  });
  return response.json();
}

// Cancel a pending trade authorization
export async function cancelTrade(userId: string, tradeAuthId: string): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE}/trade/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ userId, tradeAuthId }),
  });
  return response.json();
}

// Get trade history
export async function getTradeHistory(
  userId: string,
  options?: { limit?: number; status?: string }
): Promise<{ trades: TradeAuthorization[] }> {
  const params = new URLSearchParams();
  if (options?.limit) params.append('limit', options.limit.toString());
  if (options?.status) params.append('status', options.status);
  
  const response = await fetch(`${API_BASE}/trade/history/${userId}?${params}`);
  return response.json();
}

// Check if user has trade PIN enabled
export async function checkTradePinStatus(userId: string): Promise<{ hasPinEnabled: boolean }> {
  const response = await fetch(`${API_BASE}/trade/pin/${userId}`);
  return response.json();
}

// Set or update trade PIN
export async function setTradePin(
  userId: string,
  pin: string,
  currentPin?: string
): Promise<{ success: boolean; message?: string; error?: string }> {
  const response = await fetch(`${API_BASE}/trade/pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ userId, pin, currentPin }),
  });
  return response.json();
}
