/**
 * GetRecommendation.tsx - On-Demand Stock Recommendation Page
 * 
 * Allows users to search for any stock and generate an on-demand recommendation
 * without saving the stock to their watchlist or the recommendation to the database.
 * 
 * Features:
 * - Stock search similar to watchlist search in onboarding
 * - "Get Recommendation" button to trigger on-demand generation
 * - Displays recommendation in same UI format as StockRecommendations page
 * - Does NOT save stock to watchlist or recommendation to database
 * - Clears previous results when generating new recommendation
 */

import { useState, useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import Header from '../components/Header'
import api, { regimeApi, RegimeResponse } from '../services/api'
import RegimeDisplay from '../components/RegimeDisplay'
import { searchStocks } from '../services/onboardingApi'

interface StockSearchResult {
  symbol: string
  name: string
  exchange: string
  type: string
}

interface OnDemandRecommendation {
  // For table rendering parity with StockRecommendations
  id: string
  symbol: string
  companyName: string
  action: 'BUY' | 'SELL' | 'HOLD'
  score: number | null
  normalizedScore: number
  confidence: number
  priceAtRecommendation: number | null
  newsSentimentScore: number | null
  newsMomentumScore: number | null
  technicalTrendScore: number | null
  technicalMomentumScore: number | null
  explanation: any
  // Optional regime fields returned by the on-demand endpoint
  regime?: any
  signalWeights?: any
  generatedAt: string
}

/**
 * Score bar component for displaying individual component scores
 */
/**
 * Format a date string to a readable format in PST timezone
 */
function formatDate(dateString: string | null): string {
  if (!dateString) return '-'
  const date = new Date(dateString)
  return date.toLocaleString('en-US', {
    timeZone: 'UTC',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }) + ' PST'
}

/**
 * Format a number to a percentage string
 */
function formatPercent(value: number | null, decimals: number = 1): string {
  if (value === null || value === undefined) return '-'
  return `${(value * 100).toFixed(decimals)}%`
}

/**
 * Format a number to a fixed decimal string
 */
function formatNumber(value: number | null, decimals: number = 2): string {
  if (value === null || value === undefined) return '-'
  return value.toFixed(decimals)
}

/**
 * Format price with dollar sign
 */
function formatPrice(value: number | null): string {
  if (value === null || value === undefined) return '-'
  return `$${value.toFixed(2)}`
}

/**
 * Get the CSS classes for the action badge
 */
function getActionBadgeClasses(action: string): string {
  const baseClasses = 'inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold'
  switch (action) {
    case 'BUY':
      return `${baseClasses} bg-green-100 text-green-800`
    case 'SELL':
      return `${baseClasses} bg-red-100 text-red-800`
    case 'HOLD':
      return `${baseClasses} bg-yellow-100 text-yellow-800`
    default:
      return `${baseClasses} bg-gray-100 text-gray-800`
  }
}

/**
 * Get the confidence level indicator
 */
function getConfidenceIndicator(confidence: number | null): { label: string; color: string } {
  if (confidence === null) return { label: 'Unknown', color: 'text-gray-500' }
  if (confidence >= 0.8) return { label: 'High', color: 'text-green-600' }
  if (confidence >= 0.6) return { label: 'Medium', color: 'text-yellow-600' }
  return { label: 'Low', color: 'text-red-600' }
}

/**
 * Score bar component for visualizing scores
 */
function ScoreBar({ value, label }: { value: number | null; label: string }) {
  if (value === null) {
    return (
      <div className="flex items-center space-x-2">
        <span className="text-xs text-gray-500 w-20">{label}</span>
        <span className="text-xs text-gray-400">-</span>
      </div>
    )
  }
  
  // Normalize value to 0-100 for display (assuming -1 to 1 range)
  const normalizedValue = ((value + 1) / 2) * 100
  const barColor = value > 0 ? 'bg-green-500' : value < 0 ? 'bg-red-500' : 'bg-gray-400'
  
  return (
    <div className="flex items-center space-x-2">
      <span className="text-xs text-gray-500 w-20">{label}</span>
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden max-w-24">
        <div 
          className={`h-full ${barColor} rounded-full transition-all`}
          style={{ width: `${Math.min(100, Math.max(0, normalizedValue))}%` }}
        />
      </div>
      <span className="text-xs text-gray-600 w-12 text-right">{formatNumber(value, 3)}</span>
    </div>
  )
}

/**
 * Tooltip Component for column headers
 */
function Tooltip({ children, text }: { children: React.ReactNode; text: string }) {
  return (
    <div className="group relative inline-flex items-center gap-1 cursor-help">
      {children}
      <svg className="w-3.5 h-3.5 text-gray-400 group-hover:text-gray-600 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      {/* Tooltip appears below to avoid z-index issues with table rows */}
      <div className="absolute top-full left-0 mt-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 whitespace-normal w-64 z-[100] shadow-xl pointer-events-none">
        {text}
        {/* Arrow pointing up */}
        <div className="absolute bottom-full left-4 border-4 border-transparent border-b-gray-900" />
      </div>
    </div>
  )
}

/**
 * Explanation Modal Component (copied from StockRecommendations for UI parity)
 */
function TopNewsModal({
  isOpen,
  onClose,
  symbol,
  articles,
}: {
  isOpen: boolean
  onClose: () => void
  symbol: string
  articles: any[]
}) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:p-0">
        {/* Backdrop */}
        <div className="fixed inset-0 transition-opacity bg-gray-500 bg-opacity-75" onClick={onClose} />

        {/* Modal */}
        <div className="relative inline-block w-full max-w-2xl p-6 my-8 overflow-hidden text-left align-middle transition-all transform bg-white shadow-xl rounded-2xl max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between mb-4 sticky top-0 bg-white pb-2 border-b border-gray-100">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Top News - {symbol}</h3>
              <p className="text-sm text-gray-500">Articles aggregated during recommendation generation</p>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {articles && articles.length > 0 ? (
            <div className="space-y-3">
              <div className="bg-gray-50 p-3 rounded-lg space-y-3 max-h-[70vh] overflow-y-auto border border-gray-200">
                {articles.map((article, idx) => (
                  <div key={idx} className="text-sm border-b border-gray-200 pb-3 last:border-0 last:pb-0">
                    {article.url ? (
                      <a
                        href={article.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 hover:underline font-medium line-clamp-2 flex items-start gap-1"
                      >
                        {article.title}
                        <svg className="w-3 h-3 flex-shrink-0 mt-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      </a>
                    ) : (
                      <p className="text-gray-700 font-medium line-clamp-2">{article.title}</p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                      {article.source && (
                        <span className="text-gray-500 text-xs bg-gray-100 px-2 py-0.5 rounded">{article.source}</span>
                      )}
                      {article.sentiment && (
                        <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                          article.sentiment === 'positive' ? 'bg-green-100 text-green-700' :
                          article.sentiment === 'negative' ? 'bg-red-100 text-red-700' :
                          'bg-gray-200 text-gray-600'
                        }`}>
                          {article.sentiment}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <button
                onClick={onClose}
                className="w-full px-4 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
              >
                Close
              </button>
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-500 italic">No news articles available for this recommendation.</p>
              <button
                onClick={onClose}
                className="mt-4 px-4 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
              >
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * Explanation Modal Component (copied from StockRecommendations for UI parity)
 */
function ExplanationModal({
  isOpen,
  onClose,
  symbol,
  explanation,
}: {
  isOpen: boolean
  onClose: () => void
  symbol: string
  explanation: any | null
}) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:p-0">
        {/* Backdrop */}
        <div className="fixed inset-0 transition-opacity bg-gray-500 bg-opacity-75" onClick={onClose} />

        {/* Modal */}
        <div className="relative inline-block w-full max-w-2xl p-6 my-8 overflow-hidden text-left align-middle transition-all transform bg-white shadow-xl rounded-2xl max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between mb-4 sticky top-0 bg-white pb-2 border-b border-gray-100">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">AI Explanation - {symbol}</h3>
              {explanation?.action && (
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mt-1 ${
                    explanation.action === 'BUY'
                      ? 'bg-green-100 text-green-800'
                      : explanation.action === 'SELL'
                      ? 'bg-red-100 text-red-800'
                      : 'bg-yellow-100 text-yellow-800'
                  }`}
                >
                  {explanation.action}
                </span>
              )}
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {explanation ? (
            <div className="space-y-5">
              {/* Score Summary */}
              {explanation.score !== undefined && (
                <div className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900">
                      {((explanation.score + 1) / 2 * 100).toFixed(0)}%
                    </div>
                    <div className="text-xs text-gray-500">Score</div>
                  </div>
                  <div className="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        explanation.score > 0.2 ? 'bg-green-500' : explanation.score < -0.2 ? 'bg-red-500' : 'bg-yellow-500'
                      }`}
                      style={{ width: `${((explanation.score + 1) / 2) * 100}%` }}
                    />
                  </div>
                </div>
              )}

              {/* LLM-Powered Summary */}
              {explanation.summary && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                    <svg className="w-4 h-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    AI Analysis
                  </h4>
                  <p className="text-gray-600 bg-blue-50 p-4 rounded-lg border border-blue-100 leading-relaxed">{explanation.summary}</p>
                </div>
              )}

              {/* Key Factors */}
              {explanation.factors && explanation.factors.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                    <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Key Factors
                  </h4>
                  <ul className="bg-green-50 p-3 rounded-lg border border-green-100 space-y-2">
                    {explanation.factors.map((factor: string, idx: number) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-gray-600">
                        <span className="text-green-500 mt-0.5 flex-shrink-0">✓</span>
                        <span>{factor}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Recent News Articles with Links */}
              {explanation.recent_articles && explanation.recent_articles.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                    <svg className="w-4 h-4 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
                    </svg>
                    Recent News ({explanation.recent_articles.length} articles)
                  </h4>
                  <div className="bg-gray-50 p-3 rounded-lg space-y-3 max-h-64 overflow-y-auto border border-gray-200">
                    {explanation.recent_articles.map((article: any, idx: number) => (
                      <div key={idx} className="text-sm border-b border-gray-200 pb-3 last:border-0 last:pb-0">
                        {article.url ? (
                          <a
                            href={article.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 hover:underline font-medium line-clamp-2 flex items-start gap-1"
                          >
                            {article.title}
                            <svg className="w-3 h-3 flex-shrink-0 mt-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                          </a>
                        ) : (
                          <p className="text-gray-700 font-medium line-clamp-2">{article.title}</p>
                        )}
                        <div className="flex items-center gap-2 mt-1.5">
                          <span className="text-gray-500 text-xs bg-gray-100 px-2 py-0.5 rounded">{article.source}</span>
                          <span
                            className={`text-xs px-2 py-0.5 rounded font-medium ${
                              article.sentiment === 'positive'
                                ? 'bg-green-100 text-green-700'
                                : article.sentiment === 'negative'
                                ? 'bg-red-100 text-red-700'
                                : 'bg-gray-200 text-gray-600'
                            }`}
                          >
                            {article.sentiment}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8">
              <svg className="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-gray-500 italic">No explanation available for this recommendation.</p>
            </div>
          )}

          <div className="mt-6 pt-4 border-t border-gray-100">
            <button
              onClick={onClose}
              className="w-full px-4 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function GetRecommendation() {
  const { user } = useAuth()

  // Explanation / News modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedExplanation, setSelectedExplanation] = useState<any | null>(null)
  const [newsModalOpen, setNewsModalOpen] = useState(false)
  const [selectedArticles, setSelectedArticles] = useState<any[]>([])

  const openExplanation = (explanation: any | null) => {
    setSelectedExplanation(explanation)
    setModalOpen(true)
  }

  const openTopNews = (articles: any[] = []) => {
    setSelectedArticles(articles)
    setNewsModalOpen(true)
  }
  
  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<StockSearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)
  
  // Selected stock state
  const [selectedStock, setSelectedStock] = useState<StockSearchResult | null>(null)
  
  // Recommendation state
  const [recommendation, setRecommendation] = useState<OnDemandRecommendation | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Regime state (same as StockRecommendations page)
  const [regime, setRegime] = useState<RegimeResponse | null>(null)
  const [regimeLoading, setRegimeLoading] = useState(false)
  const [showRegime, setShowRegime] = useState(false)
  
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Handle stock search
  const handleSearch = async (query: string) => {
    setSearchQuery(query)
    
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }
    
    if (query.length < 1) {
      setSearchResults([])
      setShowDropdown(false)
      return
    }
    
    searchTimeoutRef.current = setTimeout(async () => {
      setIsSearching(true)
      try {
        // Reuse existing onboarding stock search (calls /api/stocks/search?q=...)
        const results = await searchStocks(query)
        setSearchResults(results || [])
        setShowDropdown(true)
      } catch (err) {
        console.error('Search error:', err)
        setSearchResults([])
      } finally {
        setIsSearching(false)
      }
    }, 300)
  }

  // Handle stock selection
  const handleSelectStock = (stock: StockSearchResult) => {
    setSelectedStock(stock)
    setSearchQuery(stock.symbol)
    setShowDropdown(false)
    setRecommendation(null) // Clear previous recommendation
    setRegime(null)
    setShowRegime(false)
    setError(null)
  }

  // Generate on-demand recommendation
  const handleGetRecommendation = async () => {
    if (!selectedStock) {
      setError('Please select a stock first')
      return
    }
    
    setIsGenerating(true)
    setRegimeLoading(true)
    setError(null)
    setRecommendation(null) // Clear previous results
    setRegime(null)
    setShowRegime(false)
    
    try {
      const response = await api.post('/recommendations/on-demand', {
        symbol: selectedStock.symbol,
        companyName: selectedStock.name
      })
      
      setRecommendation(response.data)
      
      // Fetch full regime data (same as StockRecommendations page)
      try {
        const regimeData = await regimeApi.getRegime(selectedStock.symbol)
        setRegime(regimeData)
      } catch (regimeErr) {
        console.error(`Failed to fetch regime for ${selectedStock.symbol}:`, regimeErr)
      } finally {
        setRegimeLoading(false)
      }
      
    } catch (err: any) {
      console.error('Error generating recommendation:', err)
      setError(err.response?.data?.error || 'Failed to generate recommendation. Please try again.')
      setRegimeLoading(false)
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Get Stock Recommendation</h1>
          <p className="mt-2 text-gray-600">
            Search for any stock and get an instant AI-powered recommendation.
            <span className="text-gray-500 text-sm ml-2">
              (Results are not saved to your watchlist or database)
            </span>
          </p>
        </div>

        {/* Search Section */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Search Stock</h2>
          
          <div className="flex gap-4">
            {/* Search Input */}
            <div className="flex-1 relative" ref={dropdownRef}>
              <div className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => handleSearch(e.target.value)}
                  onFocus={() => searchResults.length > 0 && setShowDropdown(true)}
                  placeholder="Search by symbol or company name (e.g., AAPL, Apple)"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors"
                />
                {isSearching && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                  </div>
                )}
              </div>
              
              {/* Search Dropdown */}
              {showDropdown && searchResults.length > 0 && (
                <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                  {searchResults.map((stock) => (
                    <button
                      key={stock.symbol}
                      onClick={() => handleSelectStock(stock)}
                      className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center justify-between border-b border-gray-100 last:border-0"
                    >
                      <div>
                        <span className="font-semibold text-gray-900">{stock.symbol}</span>
                        <span className="text-gray-500 ml-2 text-sm">{stock.name}</span>
                      </div>
                      <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded">{stock.exchange}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            
            {/* Get Recommendation Button */}
            <button
              onClick={handleGetRecommendation}
              disabled={!selectedStock || isGenerating}
              className={`px-6 py-3 font-medium rounded-lg transition-colors flex items-center gap-2 ${
                !selectedStock || isGenerating
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {isGenerating ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  Generating...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  Get Recommendation
                </>
              )}
            </button>
          </div>
          
          {/* Selected Stock Display */}
          {selectedStock && (
            <div className="mt-4 p-4 bg-blue-50 rounded-lg flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
                  {selectedStock.symbol.slice(0, 2)}
                </div>
                <div>
                  <span className="font-semibold text-gray-900">{selectedStock.symbol}</span>
                  <p className="text-sm text-gray-600">{selectedStock.name}</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setSelectedStock(null)
                  setSearchQuery('')
                  setRecommendation(null)
                  setError(null)
                }}
                className="text-gray-400 hover:text-gray-600 p-2"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          )}
          
          {/* Popular Stocks Suggestion */}
          {!selectedStock && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg">
              <p className="text-sm font-medium text-gray-700 mb-3">💡 Popular stocks to try:</p>
              <div className="flex flex-wrap gap-2">
                {['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX'].map((symbol) => (
                  <button
                    key={symbol}
                    onClick={() => handleSelectStock({ symbol, name: symbol, exchange: 'NASDAQ', type: 'EQUITY' })}
                    className="px-3 py-1 bg-white border border-gray-200 rounded-full text-sm font-medium text-gray-700 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700 transition-colors"
                  >
                    {symbol}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-red-800">{error}</span>
            </div>
          </div>
        )}

        {/* Generating State */}
        {isGenerating && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
            <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Generating Recommendation</h3>
            <p className="text-gray-500">
              Analyzing {selectedStock?.symbol} using news sentiment, technical indicators, and market data...
            </p>
          </div>
        )}

        {/* Recommendation Results - render using the same table as StockRecommendations */}
        {recommendation && !isGenerating && (
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            {/* Section Header */}
            <div className="bg-gradient-to-r from-gray-50 to-white border-b border-gray-200 px-6 py-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 leading-7">{recommendation.symbol}</h2>
                  <p className="text-xs text-gray-400 truncate">{recommendation.companyName}</p>
                </div>
                <div className="flex items-center gap-2">
                  {regime ? (
                    <button
                      onClick={() => setShowRegime(!showRegime)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-all whitespace-nowrap ${
                        regime.regime.risk_level === 'high'
                          ? 'bg-red-100 text-red-800 hover:bg-red-200'
                          : 'bg-blue-100 text-blue-800 hover:bg-blue-200'
                      }`}
                      title="Click to view full regime details"
                    >
                      {regime.regime.risk_level === 'high' ? '⚠️' : '📊'}
                      {regime.regime.label}
                      <svg
                        className={`w-3.5 h-3.5 transition-transform ${showRegime ? 'rotate-180' : ''}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                  ) : regimeLoading ? (
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-gray-100 text-gray-500">
                      <div className="animate-spin w-3 h-3 border border-gray-400 border-t-transparent rounded-full"></div>
                      Loading...
                    </span>
                  ) : null}
                </div>
              </div>
            </div>

            {/* Regime Details Panel (collapsible) */}
            {showRegime && regime && (
              <div className="border-b border-gray-200 p-4 bg-gray-50/50">
                <RegimeDisplay regime={regime} isLoading={regimeLoading} />
              </div>
            )}

            {/* Recommendations table (single row) */}
            <div>
              <table className="min-w-full table-auto divide-y divide-gray-200">
                <thead className="bg-gray-50 relative z-10">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      <Tooltip text="The exact date and time when this recommendation was generated by the AI system.">
                        Date & Time
                      </Tooltip>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      <Tooltip text="AI's recommended action: BUY (score > 80%), SELL (score < 50%), or HOLD (50-80%). Based on combined analysis of news sentiment and technical indicators.">
                        Action
                      </Tooltip>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      <Tooltip text="Normalized score (0-100%) representing the strength of the recommendation. Higher scores indicate stronger buy signals, lower scores indicate stronger sell signals.">
                        Score
                      </Tooltip>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      <Tooltip text="How confident the AI is in this recommendation (0-100%). Higher confidence means news and technical signals agree, multiple data sources available, and strong signals.">
                        Confidence
                      </Tooltip>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      <Tooltip text="Stock price at the exact moment when this recommendation was generated.">
                        Price
                      </Tooltip>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      <Tooltip text="Individual component scores: News (sentiment analysis), Momentum (sentiment trend), Trend (price direction using moving averages), Tech Mom. (RSI, MACD signals). Each ranges from -1 (bearish) to +1 (bullish).">
                        Component Scores
                      </Tooltip>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      <Tooltip text="View the top news articles aggregated by the recommendation engine for this run.">
                        Top News
                      </Tooltip>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      <Tooltip text="Click to view detailed AI-generated explanation of the factors that contributed to this recommendation.">
                        Explanation
                      </Tooltip>
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {(() => {
                    const rec = recommendation
                    const confidenceInfo = getConfidenceIndicator(rec.confidence)
                    return (
                      <tr key={rec.id} className="bg-blue-50">
                        <td className="px-4 py-4 align-top">
                          <div className="text-sm text-gray-900">{formatDate(rec.generatedAt)}</div>
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 mt-1">
                            Latest
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap align-top">
                          <span className={getActionBadgeClasses(rec.action)}>{rec.action}</span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap align-top">
                          <div className="text-sm">
                            <div className="font-medium text-gray-900">
                              {rec.normalizedScore !== null && !isNaN(rec.normalizedScore)
                                ? `${(rec.normalizedScore * 100).toFixed(1)}%`
                                : '-'}
                            </div>
                            <div className="text-xs text-gray-500">Raw: {formatNumber(rec.score, 3)}</div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap align-top">
                          <div className="flex items-center">
                            <div className="w-16 h-2 bg-gray-200 rounded-full mr-2">
                              <div
                                className="h-full bg-blue-600 rounded-full"
                                style={{ width: `${(rec.confidence || 0) * 100}%` }}
                              />
                            </div>
                            <span className={`text-sm font-medium ${confidenceInfo.color}`}>{formatPercent(rec.confidence)}</span>
                          </div>
                          <div className={`text-xs ${confidenceInfo.color}`}>{confidenceInfo.label}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap align-top">
                          <div className="text-sm font-medium text-gray-900">{formatPrice(rec.priceAtRecommendation)}</div>
                        </td>
                        <td className="px-4 py-4 align-top">
                          <div className="space-y-1">
                            <ScoreBar value={rec.newsSentimentScore} label="News" />
                            <ScoreBar value={rec.newsMomentumScore} label="Momentum" />
                            <ScoreBar value={rec.technicalTrendScore} label="Trend" />
                            <ScoreBar value={rec.technicalMomentumScore} label="Tech Mom." />
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap align-top">
                          <button
                            onClick={() => openTopNews(rec.explanation?.recent_articles || [])}
                            className={`text-sm font-medium ${
                              rec.explanation?.recent_articles && rec.explanation.recent_articles.length > 0
                                ? 'text-blue-600 hover:text-blue-800 hover:underline'
                                : 'text-gray-300 cursor-not-allowed'
                            }`}
                            disabled={!rec.explanation?.recent_articles || rec.explanation.recent_articles.length === 0}
                          >
                            {rec.explanation?.recent_articles && rec.explanation.recent_articles.length > 0
                              ? `View (${rec.explanation.recent_articles.length})`
                              : 'None'}
                          </button>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap align-top">
                          <button
                            onClick={() => openExplanation(rec.explanation)}
                            className="text-blue-600 hover:text-blue-800 hover:underline text-sm font-medium"
                          >
                            Explanation Link
                          </button>
                        </td>
                      </tr>
                    )
                  })()}
                </tbody>
              </table>
            </div>

            {/* Footer Note */}
            <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
              <p className="text-sm text-gray-500 flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                This recommendation is generated on-demand and is not saved. Click "Get Recommendation" again to refresh.
              </p>
            </div>

            {/* Top News Modal */}
            <TopNewsModal
              isOpen={newsModalOpen}
              onClose={() => setNewsModalOpen(false)}
              symbol={recommendation.symbol}
              articles={selectedArticles}
            />

            {/* Explanation Modal */}
            <ExplanationModal
              isOpen={modalOpen}
              onClose={() => setModalOpen(false)}
              symbol={recommendation.symbol}
              explanation={selectedExplanation}
            />
          </div>
        )}
      </main>
    </div>
  )
}
