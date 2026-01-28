import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Header from '../components/Header'
import OnboardingStatusCard from '../components/OnboardingStatusCard'
import TradeConfirmationModal from '../components/TradeConfirmationModal'
import { getOnboardingData, WatchlistStock, BrokerageConnection, TradeDetails } from '../services/onboardingApi'
import { recommendationApi, stockQuotesApi, StockQuote } from '../services/api'

interface StockDisplay {
  id: string
  symbol: string
  company_name: string
  exchange: string
  action: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  price: number
  priceChange: number | null
  priceChangePercent: number | null
  priceLoading: boolean
  hasRecommendation: boolean
}

type SortField = 'symbol' | 'action' | null
type SortDirection = 'asc' | 'desc'

export default function Dashboard() {
  const [stocks, setStocks] = useState<StockDisplay[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [brokerageConnections, setBrokerageConnections] = useState<BrokerageConnection[]>([])
  const [isTradeModalOpen, setIsTradeModalOpen] = useState(false)
  const [selectedTrade, setSelectedTrade] = useState<TradeDetails | null>(null)
  const [sortField, setSortField] = useState<SortField>(null)
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')
  const { user } = useAuth()
  const navigate = useNavigate()
  
  const [isPriceRefreshing, setIsPriceRefreshing] = useState(false)

  // Handle column sorting
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      // Toggle direction if same field
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      // New field, start with ascending
      setSortField(field)
      setSortDirection('asc')
    }
  }

  // Sort stocks based on current sort settings
  const sortedStocks = [...stocks].sort((a, b) => {
    if (!sortField) return 0
    
    let comparison = 0
    if (sortField === 'symbol') {
      comparison = a.symbol.localeCompare(b.symbol)
    } else if (sortField === 'action') {
      // Sort order: BUY > SELL > HOLD > Pending
      const actionOrder = { 'BUY': 0, 'SELL': 1, 'HOLD': 2 }
      const aOrder = a.hasRecommendation ? actionOrder[a.action] : 3
      const bOrder = b.hasRecommendation ? actionOrder[b.action] : 3
      comparison = aOrder - bOrder
    }
    
    return sortDirection === 'asc' ? comparison : -comparison
  })

  // Sort indicator component
  const SortIndicator = ({ field }: { field: SortField }) => {
    if (sortField !== field) {
      return (
        <svg className="w-4 h-4 text-gray-400 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
      )
    }
    return sortDirection === 'asc' ? (
      <svg className="w-4 h-4 text-blue-600 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
      </svg>
    ) : (
      <svg className="w-4 h-4 text-blue-600 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    )
  }

  const userId = user?.dbId || user?.sub || ''

  // Refresh prices for all stocks in the watchlist
  const handleRefreshPrices = useCallback(async () => {
    if (stocks.length === 0 || isPriceRefreshing) return
    
    setIsPriceRefreshing(true)
    
    // Set all stocks to loading state
    setStocks(prevStocks => 
      prevStocks.map(stock => ({
        ...stock,
        priceLoading: true,
      }))
    )
    
    try {
      const symbols = stocks.map(s => s.symbol)
      const response = await stockQuotesApi.getQuotes(symbols)
      const quotes = response.data.quotes || {}
      
      // Update stocks with new prices
      setStocks(prevStocks => 
        prevStocks.map(stock => {
          const quote = quotes[stock.symbol]
          return {
            ...stock,
            price: quote?.price ?? 0,
            priceChange: quote?.change ?? null,
            priceChangePercent: quote?.changePercent ?? null,
            priceLoading: false,
          }
        })
      )
    } catch (error) {
      console.error('Error refreshing prices:', error)
      // Reset loading state on error
      setStocks(prevStocks => 
        prevStocks.map(stock => ({
          ...stock,
          priceLoading: false,
        }))
      )
    } finally {
      setIsPriceRefreshing(false)
    }
  }, [stocks, isPriceRefreshing])

  // Fetch real-time prices for symbols (batched to avoid URL length limits)
  const fetchRealTimePrices = useCallback(async (symbols: string[]): Promise<Record<string, StockQuote>> => {
    if (symbols.length === 0) return {}
    
    const allQuotes: Record<string, StockQuote> = {}
    const batchSize = 40 // Keep under the 50 symbol API limit
    
    try {
      // Process symbols in batches
      for (let i = 0; i < symbols.length; i += batchSize) {
        const batch = symbols.slice(i, i + batchSize)
        console.log(`Fetching prices batch ${Math.floor(i / batchSize) + 1}/${Math.ceil(symbols.length / batchSize)} (${batch.length} symbols)`)
        
        const response = await stockQuotesApi.getQuotes(batch)
        const quotes = response.data.quotes || {}
        
        // Merge quotes into allQuotes
        Object.assign(allQuotes, quotes)
        
        // Small delay between batches to be respectful of rate limits
        if (i + batchSize < symbols.length) {
          await new Promise(resolve => setTimeout(resolve, 100))
        }
      }
      
      return allQuotes
    } catch (error) {
      console.error('Error fetching real-time prices:', error)
      return allQuotes // Return any quotes we've collected so far
    }
  }, [])

  // Load recommendations from database and fetch real-time prices
  const loadRecommendations = useCallback(async (watchlist: WatchlistStock[]) => {
    try {
      // Fetch recommendations for all watchlist stocks (up to 500)
      const response = await recommendationApi.getRecommendations(500)
      const recommendations = response.data.recommendations || []
      
      // Map watchlist stocks with their recommendations (prices loading initially)
      const stocksWithData: StockDisplay[] = watchlist.map(stock => {
        const rec = recommendations.find(r => r.symbol === stock.symbol)
        return {
          id: stock.id,
          symbol: stock.symbol,
          company_name: stock.company_name,
          exchange: stock.exchange,
          action: rec?.action ?? 'HOLD',
          confidence: rec?.confidence ?? rec?.normalizedScore ?? 0,
          price: 0, // Will be populated with real-time price
          priceChange: null,
          priceChangePercent: null,
          priceLoading: true,
          hasRecommendation: !!rec,
        }
      })
      
      setStocks(stocksWithData)
      
      // Fetch real-time prices in parallel
      if (stocksWithData.length > 0) {
        const symbols = stocksWithData.map(s => s.symbol)
        console.log(`Fetching real-time prices for ${symbols.length} symbols...`)
        
        try {
          const quotes = await fetchRealTimePrices(symbols)
          console.log(`Received quotes for ${Object.keys(quotes).length} symbols`)
          
          // Update stocks with real prices
          setStocks(prevStocks => 
            prevStocks.map(stock => {
              const quote = quotes[stock.symbol]
              if (quote?.price) {
                return {
                  ...stock,
                  price: quote.price,
                  priceChange: quote.change ?? null,
                  priceChangePercent: quote.changePercent ?? null,
                  priceLoading: false,
                }
              }
              return {
                ...stock,
                priceLoading: false,
              }
            })
          )
        } catch (priceError) {
          console.error('Error fetching prices:', priceError)
          // Reset loading state on error
          setStocks(prevStocks => 
            prevStocks.map(stock => ({
              ...stock,
              priceLoading: false,
            }))
          )
        }
      }
    } catch (error) {
      console.error('Error loading recommendations:', error)
      // Still try to show watchlist with prices even if recommendations fail
      const stocksWithData: StockDisplay[] = watchlist.map(stock => ({
        id: stock.id,
        symbol: stock.symbol,
        company_name: stock.company_name,
        exchange: stock.exchange,
        action: 'HOLD',
        confidence: 0,
        price: 0,
        priceChange: null,
        priceChangePercent: null,
        priceLoading: true,
        hasRecommendation: false,
      }))
      
      setStocks(stocksWithData)
      
      // Fetch real-time prices even on recommendation error
      if (stocksWithData.length > 0) {
        const symbols = stocksWithData.map(s => s.symbol)
        const quotes = await fetchRealTimePrices(symbols)
        
        setStocks(prevStocks => 
          prevStocks.map(stock => {
            const quote = quotes[stock.symbol]
            return {
              ...stock,
              price: quote?.price ?? 0,
              priceChange: quote?.change ?? null,
              priceChangePercent: quote?.changePercent ?? null,
              priceLoading: false,
            }
          })
        )
      }
    }
  }, [fetchRealTimePrices])

  // Load user's watchlist and brokerage connections
  useEffect(() => {
    async function loadData() {
      if (!userId) {
        setIsLoading(false)
        return
      }
      
      try {
        const data = await getOnboardingData(userId)
        const watchlist: WatchlistStock[] = data.watchlist || []
        
        // Load recommendations from database
        await loadRecommendations(watchlist)
        
        // Load brokerage connections
        setBrokerageConnections(data.brokerageConnections || [])
      } catch (error) {
        console.error('Error loading data:', error)
      } finally {
        setIsLoading(false)
      }
    }
    
    loadData()
  }, [userId, loadRecommendations])

  // Handle generate recommendations
  const handleGenerateRecommendations = async () => {
    const symbols = stocks.map(s => s.symbol)
    if (symbols.length === 0) {
      alert('Add stocks to your watchlist first')
      return
    }

    setIsGenerating(true)
    
    try {
      await recommendationApi.generate(symbols)
      
      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const statusResponse = await recommendationApi.getGenerationStatus()
          const status = statusResponse.data.status
          
          if (status === 'completed' || status === 'failed' || status === 'idle') {
            clearInterval(pollInterval)
            setIsGenerating(false)
            
            if (status === 'completed') {
              // Reload recommendations
              const data = await getOnboardingData(userId)
              const watchlist: WatchlistStock[] = data.watchlist || []
              await loadRecommendations(watchlist)
            } else if (status === 'failed') {
              console.error('Recommendation generation failed:', statusResponse.data.errorMessage)
            }
          }
        } catch (error) {
          console.error('Error polling generation status:', error)
        }
      }, 3000) // Poll every 3 seconds
      
      // Timeout after 5 minutes
      setTimeout(() => {
        clearInterval(pollInterval)
        setIsGenerating(false)
      }, 300000)
      
    } catch (error) {
      console.error('Error triggering recommendation generation:', error)
      setIsGenerating(false)
    }
  }

  const handleExecuteTrade = (stock: StockDisplay) => {
    // Check if user has a connected brokerage
    if (brokerageConnections.length === 0) {
      alert('Please connect a brokerage account first in Settings.')
      navigate('/onboarding')
      return
    }
    
    // Use the first active connection
    const connection = brokerageConnections[0]
    
    setSelectedTrade({
      symbol: stock.symbol,
      action: stock.action === 'HOLD' ? 'BUY' : stock.action,
      quantity: 1, // Default quantity
      orderType: 'market',
      brokerageConnectionId: connection.id,
      institutionName: connection.institution_name,
    })
    setIsTradeModalOpen(true)
  }

  const handleTradeSuccess = (execution: any) => {
    console.log('Trade executed:', execution)
    // Could refresh data or show notification here
  }

  const getActionColor = (action: string) => {
    switch (action) {
      case 'BUY': return 'bg-green-100 text-green-800'
      case 'SELL': return 'bg-red-100 text-red-800'
      case 'HOLD': return 'bg-yellow-100 text-yellow-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Left Sidebar */}
          <div className="lg:col-span-1 space-y-6">
            {/* Onboarding Status Card */}
            <OnboardingStatusCard userId={userId} />

            {/* Quick Actions */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h3>
              <div className="space-y-3">
                <button 
                  onClick={() => navigate('/get-recommendation')}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left text-gray-700 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors"
                >
                  <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  <span className="font-medium">Get Recommendation</span>
                </button>
                <button className="w-full flex items-center gap-3 px-4 py-3 text-left text-gray-700 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
                  <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <span className="font-medium">View Analytics</span>
                </button>
                <button 
                  onClick={() => navigate('/onboarding')}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left text-gray-700 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors"
                >
                  <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                  </svg>
                  <span className="font-medium">Manage Watchlist</span>
                </button>
                <button 
                  onClick={() => navigate('/connectors')}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left text-gray-700 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors"
                >
                  <svg className="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span className="font-medium">Data Connectors</span>
                </button>
              </div>
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-3 space-y-6">
            {/* Stats Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-gray-500">Portfolio Value</p>
                  <span className="p-2 bg-blue-50 rounded-lg">
                    <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </span>
                </div>
                <p className="text-2xl font-bold text-gray-900">$124,532</p>
                <p className="text-sm text-green-600 flex items-center gap-1 mt-1">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                  </svg>
                  +2.4% today
                </p>
              </div>
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-gray-500">Today's P&L</p>
                  <span className="p-2 bg-green-50 rounded-lg">
                    <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                    </svg>
                  </span>
                </div>
                <p className="text-2xl font-bold text-green-600">+$2,847</p>
                <p className="text-sm text-gray-500 mt-1">12 trades executed</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-gray-500">Watchlist</p>
                  <span className="p-2 bg-purple-50 rounded-lg">
                    <svg className="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                    </svg>
                  </span>
                </div>
                <p className="text-2xl font-bold text-gray-900">{stocks.length}</p>
                <p className="text-sm text-gray-500 mt-1">Stocks tracked</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-gray-500">Win Rate</p>
                  <span className="p-2 bg-yellow-50 rounded-lg">
                    <svg className="w-4 h-4 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                    </svg>
                  </span>
                </div>
                <p className="text-2xl font-bold text-gray-900">73.2%</p>
                <p className="text-sm text-gray-500 mt-1">Last 30 days</p>
              </div>
            </div>

            {/* Recommendations Table */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">AI Recommendations</h2>
                  <p className="text-sm text-gray-500">Real-time trading signals for your watchlist</p>
                </div>
                <div className="flex items-center gap-3">
                  {isGenerating ? (
                    <span className="flex items-center gap-2 text-sm text-blue-600 bg-blue-50 px-3 py-1 rounded-full">
                      <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                      Calculating...
                    </span>
                  ) : stocks.length > 0 ? (
                    <span className="flex items-center gap-2 text-sm text-green-600 bg-green-50 px-3 py-1 rounded-full">
                      <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                      Live
                    </span>
                  ) : null}
                  {stocks.length > 0 && (
                    <>
                      <button
                        onClick={handleRefreshPrices}
                        disabled={isPriceRefreshing || isGenerating}
                        className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                          isPriceRefreshing || isGenerating
                            ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                        title="Refresh real-time prices"
                      >
                        <svg className={`w-4 h-4 ${isPriceRefreshing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        {isPriceRefreshing ? 'Refreshing...' : 'Refresh Prices'}
                      </button>
                      <button
                        onClick={handleGenerateRecommendations}
                        disabled={isGenerating}
                        className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                          isGenerating
                            ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                            : 'bg-blue-600 text-white hover:bg-blue-700'
                        }`}
                      >
                        <svg className={`w-4 h-4 ${isGenerating ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        {isGenerating ? 'Generating...' : 'Generate Recommendations'}
                      </button>
                    </>
                  )}
                </div>
              </div>
              
              {isLoading ? (
                <div className="p-12 text-center">
                  <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                  <p className="text-gray-500">Loading your watchlist...</p>
                </div>
              ) : stocks.length === 0 ? (
                <div className="p-12 text-center">
                  <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No stocks in your watchlist</h3>
                  <p className="text-gray-500 mb-4">Add stocks to your watchlist to get AI-powered trading recommendations.</p>
                  <button
                    onClick={() => navigate('/onboarding')}
                    className="px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Add Stocks to Watchlist
                  </button>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th 
                          className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 transition-colors select-none"
                          onClick={() => handleSort('symbol')}
                        >
                          <div className="flex items-center">
                            Symbol
                            <SortIndicator field="symbol" />
                          </div>
                        </th>
                        <th 
                          className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 transition-colors select-none"
                          onClick={() => handleSort('action')}
                        >
                          <div className="flex items-center">
                            Action
                            <SortIndicator field="action" />
                          </div>
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Confidence</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          <span title="Real-time market price from Yahoo Finance">Current Price</span>
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {sortedStocks.map((stock) => (
                        <tr key={stock.id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
                                {stock.symbol.slice(0, 2)}
                              </div>
                              <div>
                                <span className="font-semibold text-gray-900">{stock.symbol}</span>
                                <p className="text-xs text-gray-500 truncate max-w-[150px]">{stock.company_name}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            {isGenerating ? (
                              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 flex items-center gap-1">
                                <div className="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                                Calculating
                              </span>
                            ) : stock.hasRecommendation ? (
                              <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getActionColor(stock.action)}`}>
                                {stock.action}
                              </span>
                            ) : (
                              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-500" title="No recommendation generated yet">
                                Pending
                              </span>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            {isGenerating ? (
                              <div className="flex items-center gap-2">
                                <div className="w-20 bg-gray-200 rounded-full h-2 overflow-hidden">
                                  <div className="h-2 bg-blue-400 rounded-full animate-pulse" style={{ width: '60%' }} />
                                </div>
                                <span className="text-sm font-medium text-gray-400">--</span>
                              </div>
                            ) : (
                              <div className="flex items-center gap-2">
                                <div className="w-20 bg-gray-200 rounded-full h-2">
                                  <div 
                                    className={`h-2 rounded-full ${
                                      stock.confidence >= 0.8 ? 'bg-green-500' : 
                                      stock.confidence >= 0.6 ? 'bg-yellow-500' : 'bg-red-500'
                                    }`}
                                    style={{ width: `${stock.confidence * 100}%` }}
                                  />
                                </div>
                                <span className="text-sm font-medium text-gray-600">{(stock.confidence * 100).toFixed(0)}%</span>
                              </div>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            {stock.priceLoading ? (
                              <div className="flex items-center gap-2">
                                <div className="w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin"></div>
                                <span className="text-gray-400">Loading...</span>
                              </div>
                            ) : stock.price > 0 ? (
                              <div>
                                <span className="font-medium text-gray-900">${stock.price.toFixed(2)}</span>
                                {stock.priceChange !== null && (
                                  <p className={`text-xs ${stock.priceChange >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                    {stock.priceChange >= 0 ? '+' : ''}{stock.priceChange.toFixed(2)} ({stock.priceChangePercent?.toFixed(2)}%)
                                  </p>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex gap-2">
                              <button 
                                onClick={() => handleExecuteTrade(stock)}
                                disabled={isGenerating}
                                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                                  isGenerating
                                    ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                                    : 'text-white bg-blue-600 hover:bg-blue-700'
                                }`}
                              >
                                Execute
                              </button>
                              <button 
                                onClick={() => navigate(`/recommendations/${stock.symbol}`)}
                                disabled={isGenerating}
                                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                                  isGenerating
                                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                    : 'text-gray-600 bg-gray-100 hover:bg-gray-200'
                                }`}
                              >
                                Details
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Trade Confirmation Modal */}
      <TradeConfirmationModal
        isOpen={isTradeModalOpen}
        onClose={() => {
          setIsTradeModalOpen(false)
          setSelectedTrade(null)
        }}
        onSuccess={handleTradeSuccess}
        userId={userId}
        trade={selectedTrade}
      />
    </div>
  )
}
