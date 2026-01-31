/**
 * services/api.ts - API Client Layer for v1 Endpoints
 * 
 * This module provides a centralized HTTP client for /api/v1 backend endpoints.
 * It uses Axios with pre-configured settings for the AutoTrader AI platform.
 * 
 * API Structure:
 * - /api/v1/* routes: Recommendations, connectors, health-check settings (this file)
 * - /api/* routes: User auth, onboarding, brokerage, trades (see onboardingApi.ts)
 * 
 * Architecture:
 * - Single Axios instance with base configuration
 * - Organized into logical API groups (recommendations, config, trade, connectors)
 * - TypeScript generics for response typing
 * - Credential handling for session cookies
 * 
 * Base Configuration:
 * - baseURL: '/api/v1' (proxied to backend in development via Vite)
 * - withCredentials: true (sends cookies for session management)
 * 
 * Error Handling:
 * - 401 responses should trigger re-authentication
 * - Network errors should show user-friendly messages
 * - Consider adding response interceptors for global error handling
 * 
 * @see onboardingApi.ts for user/auth/onboarding/trade endpoints
 * @see types/index.ts for response type definitions
 * @see vite.config.ts for proxy configuration
 */
import axios from 'axios'
import { UserConfig, RecommendationHistoryResponse, ConnectorStatusResponse, ConnectorSummary, StockRecommendationHistory, RegimeResponse } from '../types'

/**
 * Axios instance configured for AutoTrader AI backend v1 endpoints.
 * 
 * Configuration:
 * - baseURL: All requests prefixed with '/api/v1'
 * - withCredentials: Include cookies in cross-origin requests
 *   (required for session-based auth with separate frontend/backend)
 * 
 * In development, Vite proxies '/api' to the backend server (port 3001).
 * In production, both are served from the same origin.
 * In Docker, the web-app container proxies to the api-gateway container.
 */
const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,  // Send cookies with requests for session handling
})

/**
 * Recommendation API endpoints.
 * 
 * Fetches AI-generated trading recommendations from the
 * Recommendation Service (Java) which queries the ML pipeline output.
 */
export const recommendationApi = {
  /**
   * Get latest recommendations for the user's watchlist.
   * 
   * Recommendations are pre-computed by the ML pipeline and
   * stored in PostgreSQL. This endpoint retrieves the most recent ones.
   * 
   * @param limit Maximum number of recommendations to return (default: 5)
   * @returns Array of Recommendation objects with actions and explanations
   */
  getRecommendations: (limit: number = 5) =>
    api.get<{ recommendations: StockRecommendationHistory[] }>('/recommendations', { params: { limit } }),
  
  /**
   * Get historical recommendations for a specific stock symbol.
   * 
   * Returns the last 10 recommendations stored in the database for the
   * given symbol. The ML pipeline generates new recommendations every
   * 2 hours and keeps the last 10 per symbol.
   * 
   * Scoring System:
   * - BUY: normalized score > 0.8
   * - SELL: normalized score < 0.5
   * - HOLD: 0.5 <= normalized score <= 0.8
   * 
   * @param symbol Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
   * @param limit Maximum number of recommendations to return (default: 10)
   * @returns RecommendationHistoryResponse with list of historical recommendations
   * 
   * @see StockRecommendations.tsx for display component
   */
  getHistory: (symbol: string, limit: number = 10) =>
    api.get<RecommendationHistoryResponse>(`/recommendations/history/${symbol.toUpperCase()}`, { 
      params: { limit } 
    }),
  
  /**
   * Trigger manual recommendation generation.
   * Starts the recommendation flow service to generate new recommendations.
   * 
   * @param symbols Optional array of symbols to generate for (defaults to all watchlist)
   */
  generate: (symbols?: string[]) =>
    api.post<{ success: boolean; message: string; startedAt: string; runId?: string }>(
      '/recommendations/generate',
      { symbols }
    ),
  
  /**
   * Get the status of recommendation generation.
   * Used to poll for completion and show "Calculating" state.
   */
  getGenerationStatus: (runId?: string) =>
    runId
      ? api.get<{
          runId: string;
          status: 'idle' | 'running' | 'completed' | 'failed';
          startedAt?: string;
          completedAt?: string;
          symbols?: string[];
          errorMessage?: string;
        }>(`/recommendations/generation-status/${runId}`)
      : api.get<{
          status: 'idle' | 'running' | 'completed' | 'failed';
          startedAt?: string;
          completedAt?: string;
          symbols?: string[];
          errorMessage?: string;
        }>('/recommendations/generation-status'),
}

/**
 * Regime Classification API endpoints.
 * 
 * Fetches market regime classification from the ML Recommendation Engine.
 * The regime model analyzes market conditions and provides:
 * - Regime classification (volatility, trend, liquidity, information)
 * - Regime-adaptive signal weights
 * - Position sizing recommendations
 * - Stop-loss recommendations
 */
export const regimeApi = {
  /**
   * Get current market regime for a symbol.
   * 
   * Classifies market conditions across 4 dimensions:
   * - Volatility: low / normal / high / extreme
   * - Trend: strong_uptrend / uptrend / mean_reverting / choppy / downtrend / strong_downtrend
   * - Liquidity: high / normal / thin / illiquid
   * - Information: quiet / normal / news_driven / social_driven / earnings
   * 
   * @param symbol Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
   * @returns RegimeResponse with classification, weights, and risk management recommendations
   * 
   * @see RegimeDisplay.tsx for display component
   */
  getRegime: async (symbol: string): Promise<RegimeResponse> => {
    // Proxied through Vite to recommendation engine service
    const response = await fetch(`/regime/${symbol.toUpperCase()}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch regime for ${symbol}`)
    }
    return response.json()
  },
}

/**
 * LLM Connector Status API endpoints.
 */
export const llmConnectorApi = {
  /**
   * Get status of all LLM connectors.
   */
  getStatus: () =>
    api.get<{
      connectors: {
        name: string;
        displayName: string;
        modelName: string;
        tier: 'paid' | 'free';
        fallbackOrder: number;
        status: 'connected' | 'disconnected' | 'error' | 'unknown';
        statusMessage: string | null;
        lastCheckAt: string | null;
        lastSuccessAt: string | null;
        lastErrorAt: string | null;
        lastErrorMessage: string | null;
        responseTimeMs: number | null;
        requiresApiKey: boolean;
        hasApiKey: boolean;
        updatedAt: string | null;
      }[];
      lastUpdated: string | null;
    }>('/llm-connectors/status'),
  
  /**
   * Trigger manual health check for LLM connectors.
   */
  triggerRefresh: () =>
    api.post<{ success: boolean; message: string }>('/llm-connectors/refresh'),
}

/**
 * User Configuration API endpoints.
 * 
 * Manages user preferences, risk limits, and trading settings.
 * Stored in PostgreSQL user_configurations table.
 */
export const configApi = {
  /**
   * Get user's current configuration.
   * Called on Settings page load and for recommendation filtering.
   */
  getConfig: () =>
    api.get<UserConfig>('/config'),
  
  /**
   * Update user's configuration.
   * Saves changes made on the Settings page.
   * 
   * @param config Full UserConfig object (replaces existing)
   */
  updateConfig: (config: UserConfig) =>
    api.put('/config', config),
}

/**
 * Trade Execution API endpoints.
 * 
 * Handles trade order submission to the Trade Execution Service.
 * Requires connected brokerage account.
 * 
 * IMPORTANT: All trades require user confirmation and use
 * idempotency keys to prevent duplicate orders.
 */
export const tradeApi = {
  /**
   * Execute a trade order.
   * 
   * This sends the order to the Trade Execution Service which:
   * 1. Validates against user's risk limits
   * 2. Retrieves brokerage token from Vault
   * 3. Submits order to brokerage API (e.g., Robinhood)
   * 4. Records trade in audit log
   * 
   * @param trade Order details (symbol, side, type, quantity, price)
   * @param idempotencyKey UUID to prevent duplicate submissions
   *        Same key = same order (safe to retry on network failure)
   * @returns Trade confirmation with order ID and status
   * 
   * Security: Requires valid session AND connected brokerage.
   */
  executeTrade: (trade: {
    symbol: string
    side: 'BUY' | 'SELL'
    orderType: 'MARKET' | 'LIMIT'
    quantity: number
    limitPrice?: number  // Required for LIMIT orders
  }, idempotencyKey: string) =>
    api.post('/trades/execute', trade, {
      headers: { 'Idempotency-Key': idempotencyKey }  // Prevents duplicate orders
    }),
}

/**
 * Stock Quote Response type
 */
export interface StockQuote {
  symbol: string
  price: number | null
  previousClose: number | null
  open: number | null
  high: number | null
  low: number | null
  volume: number | null
  change: number | null
  changePercent: number | null
  fiftyTwoWeekHigh: number | null
  fiftyTwoWeekLow: number | null
  marketCap: number | null
  currency: string
  exchange: string
  lastUpdated: string
  error?: string
}

/**
 * Stock Quotes API endpoints.
 * 
 * Fetches real-time stock prices from Yahoo Finance via the API gateway.
 * These are current market prices, distinct from the historical
 * price_at_recommendation stored with recommendations.
 */
export const stockQuotesApi = {
  /**
   * Get real-time quotes for multiple symbols.
   * 
   * Fetches current market prices for up to 50 symbols at once.
   * Uses Yahoo Finance v8/finance/chart endpoint (no auth required).
   * 
   * @param symbols Array of stock symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])
   * @returns Map of symbol to quote data
   * 
   * @example
   * const { data } = await stockQuotesApi.getQuotes(['AAPL', 'MSFT'])
   * console.log(data.quotes['AAPL'].price) // Current price
   */
  getQuotes: (symbols: string[]) =>
    api.get<{
      quotes: Record<string, StockQuote>
      fetchedAt: string
      successCount: number
      errorCount: number
      errors?: { symbol: string; error: string }[]
    }>('/stocks/quotes', { params: { symbols: symbols.join(',') } }),
  
  /**
   * Get real-time quote for a single symbol.
   * 
   * @param symbol Stock ticker symbol (e.g., 'AAPL')
   * @returns Quote data with price, change, volume, etc.
   */
  getQuote: (symbol: string) =>
    api.get<StockQuote>(`/stocks/quotes/${symbol.toUpperCase()}`),
}

/**
 * Connector Status API endpoints.
 * 
 * Fetches status information for all data connectors used by the
 * recommendation engine. Status is updated by the health check service
 * every 3 hours.
 * 
 * @see Connectors.tsx for display component
 */
export const connectorApi = {
  /**
   * Get status of all data connectors.
   * 
   * Returns current health status for each connector including:
   * - Connection status (connected/disconnected/error/disabled)
   * - Last check timestamp
   * - Articles fetched count
   * - Response time
   * 
   * @returns ConnectorStatusResponse with list of connector statuses
   */
  getStatus: () =>
    api.get<ConnectorStatusResponse>('/connectors/status'),
  
  /**
   * Get summary statistics for connectors.
   * 
   * Returns counts of connectors by status for dashboard display.
   * 
   * @returns ConnectorSummary with counts by status
   */
  getSummary: () =>
    api.get<ConnectorSummary>('/connectors/summary'),
  
  /**
   * Trigger a manual health check for all connectors.
   * 
   * Spawns the health check service in the background to test
   * all connectors and update their status. Results will be
   * available after ~2-3 minutes.
   * 
   * @returns Success message
   */
  triggerRefresh: () =>
    api.post<{ success: boolean; message: string }>('/connectors/refresh'),
}

/**
 * Health Check Settings API endpoints.
 * Controls whether automatic health checks are enabled for data and LLM connectors.
 */
export const healthCheckSettingsApi = {
  /**
   * Get current health check toggle settings.
   */
  getSettings: () =>
    api.get<{
      dataConnectorsHealthCheck: { enabled: boolean; updatedAt: string };
      llmConnectorsHealthCheck: { enabled: boolean; updatedAt: string };
    }>('/health-check-settings'),
  
  /**
   * Update health check toggle setting.
   * @param type - 'data' or 'llm'
   * @param enabled - true to enable, false to disable
   */
  updateSetting: (type: 'data' | 'llm', enabled: boolean) =>
    api.put<{ success: boolean; setting: { key: string; enabled: boolean; updatedAt: string } }>(
      `/health-check-settings/${type}`,
      { enabled }
    ),
}

export default api
