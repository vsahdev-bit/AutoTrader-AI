import { useState, useEffect } from 'react'
import { connectorApi, llmConnectorApi, healthCheckSettingsApi } from '../services/api'
import { ConnectorStatus } from '../types'
import Header from '../components/Header'

// LLM Connector type
interface LLMConnectorStatus {
  name: string
  displayName: string
  modelName: string
  tier: 'paid' | 'free'
  fallbackOrder: number
  status: 'connected' | 'disconnected' | 'error' | 'unknown'
  statusMessage: string | null
  lastCheckAt: string | null
  lastSuccessAt: string | null
  lastErrorAt: string | null
  lastErrorMessage: string | null
  responseTimeMs: number | null
  requiresApiKey: boolean
  hasApiKey: boolean
  updatedAt: string | null
}

/**
 * Connectors Page
 * 
 * Displays the status of all data connectors used by the recommendation engine.
 * Status is updated by the health check service every 3 hours.
 * 
 * Features:
 * - Table showing connector name and connection status
 * - Color-coded status badges
 * - Summary statistics
 * - Last updated timestamp
 */
export default function Connectors() {
  const [connectors, setConnectors] = useState<ConnectorStatus[]>([])
  const [llmConnectors, setLlmConnectors] = useState<LLMConnectorStatus[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isRefreshingLLM, setIsRefreshingLLM] = useState(false)
  const [dataHealthCheckEnabled, setDataHealthCheckEnabled] = useState(true)
  const [llmHealthCheckEnabled, setLlmHealthCheckEnabled] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [llmLastUpdated, setLlmLastUpdated] = useState<string | null>(null)
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null)
  const [llmRefreshMessage, setLlmRefreshMessage] = useState<string | null>(null)

  // Default connectors list (fallback when API is unavailable)
  // When API is connected, this is replaced with real data from the database
  const defaultConnectors: ConnectorStatus[] = [
    { name: 'polygon', type: 'paid', displayName: 'Polygon.io', status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: true, hasApiKey: true, updatedAt: null },
    { name: 'alpha_vantage', type: 'paid', displayName: 'Alpha Vantage', status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: true, hasApiKey: true, updatedAt: null },
    { name: 'finnhub', type: 'paid', displayName: 'Finnhub', status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: true, hasApiKey: true, updatedAt: null },
    { name: 'newsapi', type: 'paid', displayName: 'NewsAPI', status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: true, hasApiKey: true, updatedAt: null },
    { name: 'benzinga', type: 'paid', displayName: 'Benzinga', status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: true, hasApiKey: true, updatedAt: null },
    { name: 'fmp', type: 'paid', displayName: 'Financial Modeling Prep', status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: true, hasApiKey: true, updatedAt: null },
    { name: 'nasdaq_data_link', type: 'paid', displayName: 'Nasdaq Data Link', status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: true, hasApiKey: true, updatedAt: null },
    { name: 'iex_cloud', type: 'disabled', displayName: 'IEX Cloud', status: 'disabled', statusMessage: 'Connector is disabled', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: true, hasApiKey: false, updatedAt: null },
    { name: 'yahoo_finance', type: 'free', displayName: 'Yahoo Finance', status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: false, hasApiKey: false, updatedAt: null },
    { name: 'rss_feeds', type: 'free', displayName: 'RSS Feeds', status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: false, hasApiKey: false, updatedAt: null },
    { name: 'sec_edgar', type: 'free', displayName: 'SEC EDGAR', status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: false, hasApiKey: false, updatedAt: null },
    { name: 'tipranks', type: 'free', displayName: 'TipRanks', status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: false, hasApiKey: false, updatedAt: null },
    { name: 'stocktwits', type: 'social', displayName: 'StockTwits', status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, articlesFetched: 0, responseTimeMs: null, requiresApiKey: false, hasApiKey: false, updatedAt: null },
  ]

  // Default LLM connectors list (fallback when API is unavailable)
  const defaultLLMConnectors: LLMConnectorStatus[] = [
    { name: 'openai', displayName: 'OpenAI', modelName: 'gpt-4o-mini', tier: 'paid', fallbackOrder: 1, status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, responseTimeMs: null, requiresApiKey: true, hasApiKey: false, updatedAt: null },
    { name: 'anthropic', displayName: 'Anthropic', modelName: 'claude-3-haiku', tier: 'paid', fallbackOrder: 2, status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, responseTimeMs: null, requiresApiKey: true, hasApiKey: false, updatedAt: null },
    { name: 'groq', displayName: 'Groq', modelName: 'llama-3.1-8b-instant', tier: 'free', fallbackOrder: 3, status: 'unknown', statusMessage: 'Waiting for health check', lastCheckAt: null, lastSuccessAt: null, lastErrorAt: null, lastErrorMessage: null, responseTimeMs: null, requiresApiKey: true, hasApiKey: false, updatedAt: null },
  ]

  const loadConnectorStatus = async () => {
    try {
      setIsLoading(true)
      setError(null)
      
      // Load data connectors
      try {
        const response = await connectorApi.getStatus()
        setConnectors(response.data.connectors)
        setLastUpdated(response.data.lastUpdated)
      } catch (err) {
        console.error('Error loading connector status:', err)
        setConnectors(defaultConnectors)
      }
      
      // Load LLM connectors
      try {
        const llmResponse = await llmConnectorApi.getStatus()
        setLlmConnectors(llmResponse.data.connectors)
        setLlmLastUpdated(llmResponse.data.lastUpdated)
      } catch (err) {
        console.error('Error loading LLM connector status:', err)
        setLlmConnectors(defaultLLMConnectors)
      }
      
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadConnectorStatus()
    loadHealthCheckSettings()
  }, [])

  const loadHealthCheckSettings = async () => {
    try {
      const response = await healthCheckSettingsApi.getSettings()
      setDataHealthCheckEnabled(response.data.dataConnectorsHealthCheck.enabled)
      setLlmHealthCheckEnabled(response.data.llmConnectorsHealthCheck.enabled)
    } catch (err) {
      console.error('Failed to load health check settings:', err)
    }
  }

  const handleDataHealthCheckToggle = async () => {
    const newValue = !dataHealthCheckEnabled
    try {
      await healthCheckSettingsApi.updateSetting('data', newValue)
      setDataHealthCheckEnabled(newValue)
    } catch (err) {
      console.error('Failed to update data health check setting:', err)
    }
  }

  const handleLlmHealthCheckToggle = async () => {
    const newValue = !llmHealthCheckEnabled
    try {
      await healthCheckSettingsApi.updateSetting('llm', newValue)
      setLlmHealthCheckEnabled(newValue)
    } catch (err) {
      console.error('Failed to update LLM health check setting:', err)
    }
  }

  // Poll for updates when refresh is in progress (data connectors)
  useEffect(() => {
    if (isRefreshing) {
      const interval = setInterval(loadConnectorStatus, 5000) // Poll every 5 seconds
      const timeout = setTimeout(() => {
        setIsRefreshing(false)
        setRefreshMessage(null)
      }, 180000) // Stop after 3 minutes
      
      return () => {
        clearInterval(interval)
        clearTimeout(timeout)
      }
    }
  }, [isRefreshing])

  // Poll for updates when LLM refresh is in progress
  useEffect(() => {
    if (isRefreshingLLM) {
      const interval = setInterval(loadConnectorStatus, 5000) // Poll every 5 seconds
      const timeout = setTimeout(() => {
        setIsRefreshingLLM(false)
        setLlmRefreshMessage(null)
      }, 60000) // Stop after 1 minute (LLM checks are faster)
      
      return () => {
        clearInterval(interval)
        clearTimeout(timeout)
      }
    }
  }, [isRefreshingLLM])

  const handleRefresh = async () => {
    try {
      setIsRefreshing(true)
      setRefreshMessage('Starting health check...')
      const response = await connectorApi.triggerRefresh()
      setRefreshMessage(response.data.message)
      // Reload status after a short delay
      setTimeout(() => loadConnectorStatus(), 3000)
    } catch (err) {
      console.error('Error triggering refresh:', err)
      setRefreshMessage('Backend not available. Run health check manually: python ml-services/connector_health_service.py --once')
      // Still show that we tried
      setTimeout(() => {
        setIsRefreshing(false)
        setRefreshMessage(null)
      }, 5000)
    }
  }

  const handleLLMRefresh = async () => {
    try {
      setIsRefreshingLLM(true)
      setLlmRefreshMessage('Starting LLM health check...')
      const response = await llmConnectorApi.triggerRefresh()
      setLlmRefreshMessage(response.data.message)
      // Reload status after a short delay
      setTimeout(() => loadConnectorStatus(), 3000)
    } catch (err) {
      console.error('Error triggering LLM refresh:', err)
      setLlmRefreshMessage('Backend not available. Run health check manually.')
      setTimeout(() => {
        setIsRefreshingLLM(false)
        setLlmRefreshMessage(null)
      }, 5000)
    }
  }

  // Get status badge styling
  const getStatusBadge = (status: ConnectorStatus['status']) => {
    switch (status) {
      case 'connected':
        return {
          bg: 'bg-green-100',
          text: 'text-green-800',
          dot: 'bg-green-500',
          label: 'Connected',
        }
      case 'disconnected':
        return {
          bg: 'bg-yellow-100',
          text: 'text-yellow-800',
          dot: 'bg-yellow-500',
          label: 'Disconnected',
        }
      case 'error':
        return {
          bg: 'bg-red-100',
          text: 'text-red-800',
          dot: 'bg-red-500',
          label: 'Error',
        }
      case 'disabled':
        return {
          bg: 'bg-gray-100',
          text: 'text-gray-600',
          dot: 'bg-gray-400',
          label: 'Disabled',
        }
      default:
        return {
          bg: 'bg-blue-100',
          text: 'text-blue-800',
          dot: 'bg-blue-500',
          label: 'Unknown',
        }
    }
  }

  // Get connector type badge
  const getTypeBadge = (type: ConnectorStatus['type']) => {
    switch (type) {
      case 'paid':
        return { bg: 'bg-purple-50', text: 'text-purple-700', label: 'API Key' }
      case 'free':
        return { bg: 'bg-emerald-50', text: 'text-emerald-700', label: 'Free' }
      case 'social':
        return { bg: 'bg-blue-50', text: 'text-blue-700', label: 'Social' }
      case 'disabled':
        return { bg: 'bg-gray-50', text: 'text-gray-500', label: 'Disabled' }
      default:
        return { bg: 'bg-gray-50', text: 'text-gray-600', label: type }
    }
  }

  // Calculate summary stats
  const summary = {
    connected: connectors.filter(c => c.status === 'connected').length,
    disconnected: connectors.filter(c => c.status === 'disconnected').length,
    error: connectors.filter(c => c.status === 'error').length,
    disabled: connectors.filter(c => c.status === 'disabled').length,
    unknown: connectors.filter(c => c.status === 'unknown').length,
    total: connectors.length,
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      {/* Page Title and Health Check Controls */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Data Connectors</h1>
            <p className="text-sm text-gray-500">Monitor external data source connections</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">
              Last checked: {lastUpdated ? (
                <span className="font-mono">
                  {new Date(lastUpdated).toLocaleString('en-US', { 
                    timeZone: 'America/Los_Angeles',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: true
                  })} PST
                </span>
              ) : (
                <span className="italic">Never</span>
              )}
            </span>
            {isRefreshing && refreshMessage && (
              <span className="text-sm text-blue-600 flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                {refreshMessage}
              </span>
            )}
            {/* Health Check Toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <span className="text-sm text-gray-600">Health Check Enabled</span>
              <button
                type="button"
                onClick={handleDataHealthCheckToggle}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  dataHealthCheckEnabled ? 'bg-blue-600' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    dataHealthCheckEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </label>
            <button
              onClick={handleRefresh}
              disabled={isRefreshing || !dataHealthCheckEnabled}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${
                isRefreshing || !dataHealthCheckEnabled
                  ? 'text-gray-400 bg-gray-100 cursor-not-allowed' 
                  : 'text-white bg-blue-600 hover:bg-blue-700'
              }`}
            >
              <svg className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {isRefreshing ? 'Checking...' : 'Run Health Check'}
            </button>
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        {/* Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-gray-500">Total</p>
              <span className="w-3 h-3 bg-blue-500 rounded-full"></span>
            </div>
            <p className="text-2xl font-bold text-gray-900 mt-1">{summary.total}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-gray-500">Connected</p>
              <span className="w-3 h-3 bg-green-500 rounded-full"></span>
            </div>
            <p className="text-2xl font-bold text-green-600 mt-1">{summary.connected}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-gray-500">Disconnected</p>
              <span className="w-3 h-3 bg-yellow-500 rounded-full"></span>
            </div>
            <p className="text-2xl font-bold text-yellow-600 mt-1">{summary.disconnected}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-gray-500">Error</p>
              <span className="w-3 h-3 bg-red-500 rounded-full"></span>
            </div>
            <p className="text-2xl font-bold text-red-600 mt-1">{summary.error}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-gray-500">Disabled</p>
              <span className="w-3 h-3 bg-gray-400 rounded-full"></span>
            </div>
            <p className="text-2xl font-bold text-gray-500 mt-1">{summary.disabled}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-gray-500">Unknown</p>
              <span className="w-3 h-3 bg-blue-400 rounded-full"></span>
            </div>
            <p className="text-2xl font-bold text-blue-500 mt-1">{summary.unknown}</p>
          </div>
        </div>

        {/* Connectors Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Connector Status</h2>
            <p className="text-sm text-gray-500">Health status of all data connectors used by the recommendation engine</p>
          </div>

          {isLoading ? (
            <div className="p-12 text-center">
              <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
              <p className="text-gray-500">Loading connector status...</p>
            </div>
          ) : error ? (
            <div className="p-12 text-center">
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Failed to Load</h3>
              <p className="text-gray-500 mb-4">{error}</p>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
              >
                Try Again
              </button>
            </div>
          ) : connectors.length === 0 ? (
            <div className="p-12 text-center">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Connectors Found</h3>
              <p className="text-gray-500">Connector status data is not available yet.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Connector
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider hidden sm:table-cell">
                      Type
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider hidden md:table-cell">
                      Last Check
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider hidden lg:table-cell">
                      Details
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {connectors.map((connector) => {
                    const statusBadge = getStatusBadge(connector.status)
                    const typeBadge = getTypeBadge(connector.type)
                    
                    return (
                      <tr key={connector.name} className="hover:bg-gray-50 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                              connector.status === 'connected' ? 'bg-gradient-to-br from-green-500 to-emerald-600' :
                              connector.status === 'error' ? 'bg-gradient-to-br from-red-500 to-rose-600' :
                              connector.status === 'disabled' ? 'bg-gradient-to-br from-gray-400 to-gray-500' :
                              'bg-gradient-to-br from-yellow-500 to-amber-600'
                            }`}>
                              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                {connector.status === 'connected' ? (
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                ) : connector.status === 'error' ? (
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                ) : connector.status === 'disabled' ? (
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                                ) : (
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                )}
                              </svg>
                            </div>
                            <div>
                              <p className="font-semibold text-gray-900">{connector.displayName}</p>
                              <p className="text-xs text-gray-500">{connector.name}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${statusBadge.bg} ${statusBadge.text}`}>
                            <span className={`w-2 h-2 rounded-full ${statusBadge.dot} ${connector.status === 'connected' ? 'animate-pulse' : ''}`}></span>
                            {statusBadge.label}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap hidden sm:table-cell">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium ${typeBadge.bg} ${typeBadge.text}`}>
                            {typeBadge.label}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap hidden md:table-cell">
                          <div className="text-sm">
                            {connector.lastCheckAt ? (
                              <span className="text-gray-600 font-mono">
                                {new Date(connector.lastCheckAt).toLocaleString('en-US', { 
                                  timeZone: 'America/Los_Angeles',
                                  year: 'numeric',
                                  month: '2-digit',
                                  day: '2-digit',
                                  hour: '2-digit',
                                  minute: '2-digit',
                                  second: '2-digit',
                                  hour12: true
                                })} PST
                              </span>
                            ) : (
                              <span className="text-gray-400 italic">Never</span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap hidden lg:table-cell">
                          <div className="text-sm text-gray-500">
                            {connector.status === 'connected' && connector.articlesFetched > 0 && (
                              <span className="text-green-600">{connector.articlesFetched} articles fetched</span>
                            )}
                            {connector.status === 'connected' && connector.responseTimeMs && (
                              <span className="text-gray-400 ml-2">({connector.responseTimeMs}ms)</span>
                            )}
                            {connector.status === 'error' && connector.statusMessage && (
                              <span className="text-red-600">{connector.statusMessage}</span>
                            )}
                            {connector.status === 'disconnected' && (
                              <span className="text-yellow-600">{connector.statusMessage || 'Not configured'}</span>
                            )}
                            {connector.status === 'disabled' && (
                              <span className="text-gray-500">Intentionally disabled</span>
                            )}
                            {connector.status === 'unknown' && (
                              <span className="text-blue-600">Awaiting first check</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Info Card */}
        <div className="mt-8 bg-blue-50 rounded-xl border border-blue-200 p-6">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-blue-900">About Data Connectors</h3>
              <p className="text-sm text-blue-700 mt-1">
                Data connectors fetch real-time news, market data, and sentiment from external APIs to power the AI recommendation engine.
                The health check service runs every 3 hours to verify connectivity and update status.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-1 text-xs text-blue-800 bg-blue-100 px-2 py-1 rounded">
                  <span className="w-2 h-2 bg-purple-500 rounded-full"></span>
                  API Key = Requires paid API subscription
                </span>
                <span className="inline-flex items-center gap-1 text-xs text-blue-800 bg-blue-100 px-2 py-1 rounded">
                  <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
                  Free = No API key required
                </span>
                <span className="inline-flex items-center gap-1 text-xs text-blue-800 bg-blue-100 px-2 py-1 rounded">
                  <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                  Social = Social media data source
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* LLM Connectors Table */}
        <div className="mt-8 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">LLM Connectors</h2>
              <p className="text-sm text-gray-500">AI language models for sentiment analysis (fallback order: 1 → 2 → 3)</p>
            </div>
            <div className="flex items-center gap-3">
              {llmLastUpdated && (
                <span className="text-sm text-gray-500">
                  Last checked: {new Date(llmLastUpdated).toLocaleString('en-US', { 
                    timeZone: 'America/Los_Angeles',
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: true
                  })} PST
                </span>
              )}
              {isRefreshingLLM && llmRefreshMessage && (
                <span className="text-sm text-purple-600 flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-purple-600 border-t-transparent rounded-full animate-spin"></div>
                  {llmRefreshMessage}
                </span>
              )}
              {/* Health Check Toggle */}
              <label className="flex items-center gap-2 cursor-pointer">
                <span className="text-sm text-gray-600">Health Check Enabled</span>
                <button
                  type="button"
                  onClick={handleLlmHealthCheckToggle}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    llmHealthCheckEnabled ? 'bg-purple-600' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      llmHealthCheckEnabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </label>
              <button
                onClick={handleLLMRefresh}
                disabled={isRefreshingLLM || !llmHealthCheckEnabled}
                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${
                  isRefreshingLLM || !llmHealthCheckEnabled
                    ? 'text-gray-400 bg-gray-100 cursor-not-allowed' 
                    : 'text-white bg-purple-600 hover:bg-purple-700'
                }`}
              >
                <svg className={`w-4 h-4 ${isRefreshingLLM ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {isRefreshingLLM ? 'Checking...' : 'Run Health Check'}
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Order
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Provider
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider hidden sm:table-cell">
                    Model
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider hidden md:table-cell">
                    Last Check
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider hidden lg:table-cell">
                    Details
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {llmConnectors.map((connector) => {
                  const statusBadge = getStatusBadge(connector.status)
                  
                  return (
                    <tr key={connector.name} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                          connector.fallbackOrder === 1 ? 'bg-purple-100 text-purple-700' :
                          connector.fallbackOrder === 2 ? 'bg-blue-100 text-blue-700' :
                          'bg-green-100 text-green-700'
                        }`}>
                          {connector.fallbackOrder}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                            connector.status === 'connected' ? 'bg-gradient-to-br from-purple-500 to-indigo-600' :
                            connector.status === 'error' ? 'bg-gradient-to-br from-red-500 to-rose-600' :
                            'bg-gradient-to-br from-gray-400 to-gray-500'
                          }`}>
                            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                            </svg>
                          </div>
                          <div>
                            <p className="font-semibold text-gray-900">{connector.displayName}</p>
                            <p className="text-xs text-gray-500">
                              {connector.tier === 'paid' ? (
                                <span className="text-purple-600">Paid</span>
                              ) : (
                                <span className="text-green-600">Free tier</span>
                              )}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${statusBadge.bg} ${statusBadge.text}`}>
                          <span className={`w-2 h-2 rounded-full ${statusBadge.dot} ${connector.status === 'connected' ? 'animate-pulse' : ''}`}></span>
                          {statusBadge.label}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap hidden sm:table-cell">
                        <span className="text-sm text-gray-600 font-mono">{connector.modelName}</span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap hidden md:table-cell">
                        <div className="text-sm">
                          {connector.lastCheckAt ? (
                            <span className="text-gray-600 font-mono">
                              {new Date(connector.lastCheckAt).toLocaleString('en-US', { 
                                timeZone: 'America/Los_Angeles',
                                year: 'numeric',
                                month: '2-digit',
                                day: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit',
                                hour12: true
                              })} PST
                            </span>
                          ) : (
                            <span className="text-gray-400 italic">Never</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap hidden lg:table-cell">
                        <div className="text-sm text-gray-500">
                          {connector.status === 'connected' && connector.responseTimeMs && (
                            <span className="text-green-600">{connector.responseTimeMs}ms response time</span>
                          )}
                          {connector.status === 'error' && connector.statusMessage && (
                            <span className="text-red-600">{connector.statusMessage}</span>
                          )}
                          {connector.status === 'disconnected' && (
                            <span className="text-yellow-600">{connector.statusMessage || 'No API key configured'}</span>
                          )}
                          {connector.status === 'unknown' && (
                            <span className="text-blue-600">Awaiting first check</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* LLM Info Card */}
        <div className="mt-8 bg-purple-50 rounded-xl border border-purple-200 p-6">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center flex-shrink-0">
              <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-purple-900">About LLM Connectors</h3>
              <p className="text-sm text-purple-700 mt-1">
                LLM connectors power the AI sentiment analysis for financial news. The system uses a fallback strategy:
                it tries the primary provider (OpenAI) first, and if that fails, falls back to the next provider in order.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-1 text-xs text-purple-800 bg-purple-100 px-2 py-1 rounded">
                  <span className="w-5 h-5 rounded-full bg-purple-200 text-purple-700 flex items-center justify-center text-xs font-bold">1</span>
                  OpenAI (Primary)
                </span>
                <span className="inline-flex items-center gap-1 text-xs text-purple-800 bg-purple-100 px-2 py-1 rounded">
                  <span className="w-5 h-5 rounded-full bg-blue-200 text-blue-700 flex items-center justify-center text-xs font-bold">2</span>
                  Anthropic (Fallback)
                </span>
                <span className="inline-flex items-center gap-1 text-xs text-purple-800 bg-purple-100 px-2 py-1 rounded">
                  <span className="w-5 h-5 rounded-full bg-green-200 text-green-700 flex items-center justify-center text-xs font-bold">3</span>
                  Groq (Free Fallback)
                </span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
