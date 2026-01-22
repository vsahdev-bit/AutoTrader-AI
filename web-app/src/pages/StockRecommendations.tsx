/**
 * StockRecommendations.tsx - Stock Recommendation Page
 * 
 * Displays AI-generated recommendations for all stocks in the user's watchlist.
 * Each stock has its own table section, stacked vertically.
 * 
 * Features:
 * - Shows recommendations for all watchlist stocks
 * - Each stock has its own table with header
 * - Deep linking support via URL hash (#SYMBOL) or path (/recommendations/SYMBOL)
 * - Auto-scrolls to specific stock section when accessed via deep link
 * - Color-coded actions (BUY=green, SELL=red, HOLD=yellow)
 * - Shows component scores and confidence levels
 * - Responsive design with Tailwind CSS
 * 
 * Scoring System:
 * - BUY: normalized score > 0.8
 * - SELL: normalized score < 0.5
 * - HOLD: 0.5 <= normalized score <= 0.8
 */

import { useState, useEffect, useRef } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { recommendationApi } from '../services/api'
import { getOnboardingData } from '../services/onboardingApi'
import { StockRecommendationHistory } from '../types'
import { useAuth } from '../context/AuthContext'
import Header from '../components/Header'
import api from '../services/api'

/**
 * Tooltip Component for column headers
 */
function Tooltip({ children, text }: { children: React.ReactNode; text: string }) {
  return (
    <div className="group relative inline-flex items-center gap-1 cursor-help">
      {children}
      <svg className="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 whitespace-normal w-64 z-50 shadow-lg">
        {text}
        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
      </div>
    </div>
  )
}

/**
 * Explanation Modal Component
 */
function ExplanationModal({ 
  isOpen, 
  onClose, 
  symbol, 
  explanation 
}: { 
  isOpen: boolean
  onClose: () => void
  symbol: string
  explanation: StockRecommendationHistory['explanation'] | null
}) {
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:p-0">
        {/* Backdrop */}
        <div 
          className="fixed inset-0 transition-opacity bg-gray-500 bg-opacity-75" 
          onClick={onClose}
        />
        
        {/* Modal */}
        <div className="relative inline-block w-full max-w-lg p-6 my-8 overflow-hidden text-left align-middle transition-all transform bg-white shadow-xl rounded-2xl">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">
              AI Explanation - {symbol}
            </h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          {explanation ? (
            <div className="space-y-4">
              {/* LLM-Powered Summary */}
              {explanation.summary && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-1">AI Analysis</h4>
                  <p className="text-gray-600 bg-blue-50 p-3 rounded-lg border border-blue-100">
                    {explanation.summary}
                  </p>
                </div>
              )}
              
              {/* Key Factors */}
              {explanation.factors && explanation.factors.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Key Factors</h4>
                  <ul className="bg-green-50 p-3 rounded-lg border border-green-100 space-y-2">
                    {explanation.factors.map((factor: string, idx: number) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-gray-600">
                        <span className="text-green-500 mt-0.5">✓</span>
                        <span>{factor}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              {/* Recent News Articles */}
              {(explanation as any).recent_articles && (explanation as any).recent_articles.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Recent News</h4>
                  <div className="bg-gray-50 p-3 rounded-lg space-y-2 max-h-48 overflow-y-auto">
                    {(explanation as any).recent_articles.map((article: { title: string; source: string; sentiment: string }, idx: number) => (
                      <div key={idx} className="text-sm border-b border-gray-200 pb-2 last:border-0 last:pb-0">
                        <p className="text-gray-700 font-medium line-clamp-2">{article.title}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-gray-500 text-xs">{article.source}</span>
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            article.sentiment === 'positive' ? 'bg-green-100 text-green-700' :
                            article.sentiment === 'negative' ? 'bg-red-100 text-red-700' :
                            'bg-gray-100 text-gray-600'
                          }`}>
                            {article.sentiment}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* News Analytics */}
              {explanation.news && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">News Analytics</h4>
                  <div className="bg-gray-50 p-3 rounded-lg text-sm text-gray-600 grid grid-cols-2 gap-2">
                    {explanation.news.articles_24h !== undefined && (
                      <div>
                        <span className="text-gray-500">Articles (24h):</span>
                        <span className="ml-1 font-medium">{explanation.news.articles_24h}</span>
                      </div>
                    )}
                    {explanation.news.articles_7d !== undefined && (
                      <div>
                        <span className="text-gray-500">Articles (7d):</span>
                        <span className="ml-1 font-medium">{explanation.news.articles_7d}</span>
                      </div>
                    )}
                    {explanation.news.sentiment_1d !== undefined && (
                      <div>
                        <span className="text-gray-500">Sentiment:</span>
                        <span className={`ml-1 font-medium ${
                          explanation.news.sentiment_1d > 0.1 ? 'text-green-600' :
                          explanation.news.sentiment_1d < -0.1 ? 'text-red-600' : 'text-gray-600'
                        }`}>
                          {(explanation.news.sentiment_1d * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}
                    {explanation.news.sentiment_trend && (
                      <div>
                        <span className="text-gray-500">Trend:</span>
                        <span className={`ml-1 font-medium ${
                          explanation.news.sentiment_trend === 'improving' ? 'text-green-600' :
                          explanation.news.sentiment_trend === 'declining' ? 'text-red-600' : 'text-gray-600'
                        }`}>
                          {explanation.news.sentiment_trend}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {/* Technical Analysis */}
              {explanation.technical && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Technical Analysis</h4>
                  <div className="bg-gray-50 p-3 rounded-lg text-sm text-gray-600 grid grid-cols-2 gap-2">
                    {explanation.technical.price !== undefined && (
                      <div>
                        <span className="text-gray-500">Price:</span>
                        <span className="ml-1 font-medium">${explanation.technical.price}</span>
                      </div>
                    )}
                    {explanation.technical.change_1d && (
                      <div>
                        <span className="text-gray-500">1d Change:</span>
                        <span className={`ml-1 font-medium ${
                          explanation.technical.change_1d.startsWith('-') ? 'text-red-600' : 'text-green-600'
                        }`}>
                          {explanation.technical.change_1d}
                        </span>
                      </div>
                    )}
                    {explanation.technical.rsi !== undefined && (
                      <div>
                        <span className="text-gray-500">RSI:</span>
                        <span className={`ml-1 font-medium ${
                          explanation.technical.rsi < 30 ? 'text-green-600' :
                          explanation.technical.rsi > 70 ? 'text-red-600' : 'text-gray-600'
                        }`}>
                          {typeof explanation.technical.rsi === 'number' ? explanation.technical.rsi.toFixed(0) : explanation.technical.rsi}
                        </span>
                      </div>
                    )}
                    {explanation.technical.trend && (
                      <div>
                        <span className="text-gray-500">Trend:</span>
                        <span className={`ml-1 font-medium ${
                          explanation.technical.trend === 'bullish' ? 'text-green-600' :
                          explanation.technical.trend === 'bearish' ? 'text-red-600' : 'text-gray-600'
                        }`}>
                          {explanation.technical.trend}
                        </span>
                      </div>
                    )}
                    {explanation.technical.volatility && (
                      <div>
                        <span className="text-gray-500">Volatility:</span>
                        <span className="ml-1 font-medium">{explanation.technical.volatility}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-500 italic">No explanation available for this recommendation.</p>
          )}
          
          <div className="mt-6">
            <button
              onClick={onClose}
              className="w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

interface WatchlistSymbol {
  symbol: string
  companyName: string
}

interface SymbolRecommendations {
  symbol: string
  companyName: string
  recommendations: StockRecommendationHistory[]
  loading: boolean
  error: string | null
}

/**
 * Format a date string to a readable format
 */
function formatDate(dateString: string | null): string {
  if (!dateString) return '-'
  const date = new Date(dateString)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
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
 * Single stock recommendation table component
 */
function StockRecommendationTable({ 
  data, 
  sectionRef 
}: { 
  data: SymbolRecommendations
  sectionRef: React.RefObject<HTMLDivElement>
}) {
  const { symbol, companyName, recommendations, loading, error } = data
  const latestRec = recommendations[0]
  
  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedExplanation, setSelectedExplanation] = useState<StockRecommendationHistory['explanation'] | null>(null)
  
  const openExplanation = (explanation: StockRecommendationHistory['explanation'] | null) => {
    setSelectedExplanation(explanation)
    setModalOpen(true)
  }
  
  return (
    <div 
      ref={sectionRef}
      id={symbol}
      className="bg-white rounded-xl shadow-sm overflow-hidden scroll-mt-24"
    >
      {/* Section Header */}
      <div className="bg-gradient-to-r from-gray-50 to-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-xl font-bold text-gray-900">{symbol}</h2>
              <p className="text-sm text-gray-500">{companyName}</p>
            </div>
            {latestRec && (
              <span className={getActionBadgeClasses(latestRec.action)}>
                {latestRec.action}
              </span>
            )}
          </div>
          {latestRec?.priceAtRecommendation && (
            <div className="text-right">
              <p className="text-sm text-gray-500">Latest Price</p>
              <p className="text-xl font-semibold text-gray-900">
                {formatPrice(latestRec.priceAtRecommendation)}
              </p>
            </div>
          )}
        </div>
        
        {/* Latest recommendation summary */}
        {latestRec && (
          <div className="mt-3 flex items-center gap-6 text-sm">
            <div>
              <span className="text-gray-500">Score: </span>
              <span className="font-medium text-gray-900">
                {latestRec.normalizedScore !== null && !isNaN(latestRec.normalizedScore)
                  ? `${(latestRec.normalizedScore * 100).toFixed(1)}%` 
                  : '-'}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Confidence: </span>
              <span className={`font-medium ${getConfidenceIndicator(latestRec.confidence).color}`}>
                {formatPercent(latestRec.confidence)}
              </span>
            </div>
            <div className="text-gray-500 text-xs">
              Updated: {formatDate(latestRec.generatedAt)}
            </div>
          </div>
        )}
      </div>
      
      {/* Loading state */}
      {loading && (
        <div className="p-8 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-2 text-sm text-gray-500">Loading recommendations...</p>
        </div>
      )}
      
      {/* Error state */}
      {error && !loading && (
        <div className="p-6 bg-red-50 text-center">
          <p className="text-red-600 text-sm">{error}</p>
        </div>
      )}
      
      {/* No recommendations */}
      {!loading && !error && recommendations.length === 0 && (
        <div className="p-8 text-center">
          <svg 
            className="mx-auto h-10 w-10 text-gray-400" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={1.5} 
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" 
            />
          </svg>
          <p className="mt-2 text-sm text-gray-500">
            No recommendations generated yet for {symbol}.
          </p>
        </div>
      )}
      
      {/* Recommendations table */}
      {!loading && !error && recommendations.length > 0 && (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <Tooltip text="The exact date and time when this recommendation was generated by the AI system.">
                    Date & Time
                  </Tooltip>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <Tooltip text="AI's recommended action: BUY (score > 80%), SELL (score < 50%), or HOLD (50-80%). Based on combined analysis of news sentiment and technical indicators.">
                    Action
                  </Tooltip>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <Tooltip text="Normalized score (0-100%) representing the strength of the recommendation. Higher scores indicate stronger buy signals, lower scores indicate stronger sell signals.">
                    Score
                  </Tooltip>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <Tooltip text="How confident the AI is in this recommendation (0-100%). Higher confidence means news and technical signals agree, multiple data sources available, and strong signals.">
                    Confidence
                  </Tooltip>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <Tooltip text="Stock price at the exact moment when this recommendation was generated.">
                    Price
                  </Tooltip>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <Tooltip text="Individual component scores: News (sentiment analysis), Momentum (sentiment trend), Trend (price direction using moving averages), Tech Mom. (RSI, MACD signals). Each ranges from -1 (bearish) to +1 (bullish).">
                    Component Scores
                  </Tooltip>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <Tooltip text="Click to view detailed AI-generated explanation of the factors that contributed to this recommendation.">
                    Explanation
                  </Tooltip>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {recommendations.map((rec, index) => {
                const confidenceInfo = getConfidenceIndicator(rec.confidence)
                return (
                  <tr 
                    key={rec.id} 
                    className={index === 0 ? 'bg-blue-50' : 'hover:bg-gray-50'}
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">
                        {formatDate(rec.generatedAt)}
                      </div>
                      {index === 0 && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 mt-1">
                          Latest
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={getActionBadgeClasses(rec.action)}>
                        {rec.action}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm">
                        <div className="font-medium text-gray-900">
                          {rec.normalizedScore !== null && !isNaN(rec.normalizedScore)
                            ? `${(rec.normalizedScore * 100).toFixed(1)}%` 
                            : '-'}
                        </div>
                        <div className="text-xs text-gray-500">
                          Raw: {formatNumber(rec.score, 3)}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="w-16 h-2 bg-gray-200 rounded-full mr-2">
                          <div 
                            className="h-full bg-blue-600 rounded-full"
                            style={{ width: `${(rec.confidence || 0) * 100}%` }}
                          />
                        </div>
                        <span className={`text-sm font-medium ${confidenceInfo.color}`}>
                          {formatPercent(rec.confidence)}
                        </span>
                      </div>
                      <div className={`text-xs ${confidenceInfo.color}`}>
                        {confidenceInfo.label}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {formatPrice(rec.priceAtRecommendation)}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="space-y-1 min-w-48">
                        <ScoreBar value={rec.newsSentimentScore} label="News" />
                        <ScoreBar value={rec.newsMomentumScore} label="Momentum" />
                        <ScoreBar value={rec.technicalTrendScore} label="Trend" />
                        <ScoreBar value={rec.technicalMomentumScore} label="Tech Mom." />
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <button
                        onClick={() => openExplanation(rec.explanation)}
                        className="text-blue-600 hover:text-blue-800 hover:underline text-sm font-medium"
                      >
                        Explanation Link
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      
      {/* Explanation Modal */}
      <ExplanationModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        symbol={symbol}
        explanation={selectedExplanation}
      />
    </div>
  )
}

/**
 * Main StockRecommendations component
 */
export default function StockRecommendations() {
  const { symbol: urlSymbol } = useParams<{ symbol?: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  
  // Get target symbol from URL path (/recommendations/AAPL) or hash (#AAPL)
  const targetSymbol = urlSymbol?.toUpperCase() || location.hash.replace('#', '').toUpperCase() || ''
  
  const [watchlist, setWatchlist] = useState<WatchlistSymbol[]>([])
  const [symbolData, setSymbolData] = useState<Map<string, SymbolRecommendations>>(new Map())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generateMessage, setGenerateMessage] = useState<string | null>(null)
  
  // Refs for each symbol section for scrolling
  const sectionRefs = useRef<Map<string, React.RefObject<HTMLDivElement>>>(new Map())
  
  // Fetch watchlist on mount
  useEffect(() => {
    const fetchWatchlist = async () => {
      if (!user?.dbId) {
        setError('Please log in to view recommendations')
        setLoading(false)
        return
      }
      
      try {
        const data = await getOnboardingData(user.dbId)
        const symbols = data.watchlist.map(w => ({
          symbol: w.symbol,
          companyName: w.company_name || w.symbol
        }))
        setWatchlist(symbols)
        
        // Initialize refs for each symbol
        symbols.forEach(s => {
          if (!sectionRefs.current.has(s.symbol)) {
            sectionRefs.current.set(s.symbol, { current: null } as React.RefObject<HTMLDivElement>)
          }
        })
        
        // Initialize symbol data with loading state
        const initialData = new Map<string, SymbolRecommendations>()
        symbols.forEach(s => {
          initialData.set(s.symbol, {
            symbol: s.symbol,
            companyName: s.companyName,
            recommendations: [],
            loading: true,
            error: null
          })
        })
        setSymbolData(initialData)
        
      } catch (err: any) {
        console.error('Failed to fetch watchlist:', err)
        setError('Failed to load watchlist. Please try again.')
      } finally {
        setLoading(false)
      }
    }
    
    fetchWatchlist()
  }, [user?.dbId])
  
  // Fetch recommendations for all watchlist symbols
  useEffect(() => {
    if (watchlist.length === 0) return
    
    const fetchAllRecommendations = async () => {
      for (const { symbol, companyName } of watchlist) {
        try {
          const response = await recommendationApi.getHistory(symbol, 10)
          
          setSymbolData(prev => {
            const newMap = new Map(prev)
            newMap.set(symbol, {
              symbol,
              companyName,
              recommendations: response.data.recommendations,
              loading: false,
              error: null
            })
            return newMap
          })
        } catch (err: any) {
          console.error(`Failed to fetch recommendations for ${symbol}:`, err)
          setSymbolData(prev => {
            const newMap = new Map(prev)
            newMap.set(symbol, {
              symbol,
              companyName,
              recommendations: [],
              loading: false,
              error: `Failed to load recommendations for ${symbol}`
            })
            return newMap
          })
        }
      }
    }
    
    fetchAllRecommendations()
  }, [watchlist])
  
  // Auto-scroll to target symbol section
  useEffect(() => {
    if (!targetSymbol || loading) return
    
    // Wait for DOM to update
    const timeoutId = setTimeout(() => {
      const ref = sectionRefs.current.get(targetSymbol)
      if (ref?.current) {
        ref.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, 100)
    
    return () => clearTimeout(timeoutId)
  }, [targetSymbol, loading, symbolData])
  
  // Handle quick navigation to a symbol
  const handleSymbolClick = (symbol: string) => {
    navigate(`/recommendations/${symbol}`)
    const ref = sectionRefs.current.get(symbol)
    if (ref?.current) {
      ref.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  // Handle generate recommendations on demand
  const handleGenerateRecommendations = async () => {
    setIsGenerating(true)
    setGenerateMessage('Starting recommendation generation...')
    
    try {
      await api.post('/recommendations/generate')
      setGenerateMessage('Generating recommendations... This may take a few minutes.')
      
      // Poll for updates every 10 seconds for up to 5 minutes
      let pollCount = 0
      const maxPolls = 30
      const pollInterval = setInterval(async () => {
        pollCount++
        
        // Refresh data
        for (const { symbol, companyName } of watchlist) {
          try {
            const response = await recommendationApi.getHistory(symbol, 10)
            setSymbolData(prev => {
              const newMap = new Map(prev)
              newMap.set(symbol, {
                symbol,
                companyName,
                recommendations: response.data.recommendations,
                loading: false,
                error: null
              })
              return newMap
            })
          } catch (err) {
            console.error(`Failed to refresh ${symbol}:`, err)
          }
        }
        
        if (pollCount >= maxPolls) {
          clearInterval(pollInterval)
          setIsGenerating(false)
          setGenerateMessage(null)
        }
      }, 10000)
      
      // Auto-stop after 5 minutes
      setTimeout(() => {
        clearInterval(pollInterval)
        setIsGenerating(false)
        setGenerateMessage(null)
      }, 300000)
      
    } catch (err: any) {
      console.error('Failed to generate recommendations:', err)
      setGenerateMessage('Failed to start generation. Please try again.')
      setTimeout(() => {
        setIsGenerating(false)
        setGenerateMessage(null)
      }, 3000)
    }
  }
  
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      {/* Page Title and Quick Navigation */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Stock Recommendations
              </h1>
              <p className="mt-1 text-sm text-gray-500">
                AI-generated trading recommendations for your watchlist • Updated every 2 hours (6 AM - 1 PM PST)
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              {/* Generate button */}
              {isGenerating && generateMessage && (
                <span className="text-sm text-green-600 flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin"></div>
                  {generateMessage}
                </span>
              )}
              <button
                onClick={handleGenerateRecommendations}
                disabled={isGenerating}
                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${
                  isGenerating 
                    ? 'text-gray-400 bg-gray-100 cursor-not-allowed' 
                    : 'text-white bg-green-600 hover:bg-green-700'
                }`}
                title="Generate new recommendations for all watchlist stocks immediately, regardless of schedule"
              >
                <svg className={`w-4 h-4 ${isGenerating ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                {isGenerating ? 'Generating...' : 'Generate Recommendations'}
              </button>
            </div>
          </div>
          
          {/* Quick navigation */}
          {watchlist.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-gray-100">
              <span className="text-sm text-gray-500">Jump to:</span>
              {watchlist.map(({ symbol }) => (
                <button
                  key={symbol}
                  onClick={() => handleSymbolClick(symbol)}
                  className={`px-3 py-1 text-sm rounded-full transition-colors ${
                    targetSymbol === symbol
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {symbol}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Loading state */}
        {loading && (
          <div className="bg-white rounded-xl shadow-sm p-12 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-500">Loading your watchlist...</p>
          </div>
        )}
        
        {/* Error state */}
        {error && !loading && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
            <svg 
              className="mx-auto h-12 w-12 text-red-400" 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" 
              />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-red-800">Error Loading Data</h3>
            <p className="mt-2 text-red-600">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors"
            >
              Try Again
            </button>
          </div>
        )}
        
        {/* Empty watchlist */}
        {!loading && !error && watchlist.length === 0 && (
          <div className="bg-white rounded-xl shadow-sm p-12 text-center">
            <svg 
              className="mx-auto h-16 w-16 text-gray-400" 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={1.5} 
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" 
              />
            </svg>
            <h2 className="mt-4 text-xl font-semibold text-gray-900">
              No Stocks in Watchlist
            </h2>
            <p className="mt-2 text-gray-500 max-w-md mx-auto">
              Add stocks to your watchlist during onboarding to see AI-generated 
              trading recommendations here.
            </p>
            <button
              onClick={() => navigate('/onboarding')}
              className="mt-6 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Go to Onboarding
            </button>
          </div>
        )}
        
        {/* Recommendation tables for each symbol */}
        {!loading && !error && watchlist.length > 0 && (
          <div className="space-y-8">
            {watchlist.map(({ symbol }) => {
              const data = symbolData.get(symbol)
              if (!data) return null
              
              // Get or create ref for this symbol
              let ref = sectionRefs.current.get(symbol)
              if (!ref) {
                ref = { current: null } as React.RefObject<HTMLDivElement>
                sectionRefs.current.set(symbol, ref)
              }
              
              return (
                <StockRecommendationTable 
                  key={symbol}
                  data={data}
                  sectionRef={ref}
                />
              )
            })}
            
            {/* Scoring legend */}
            <div className="bg-white rounded-xl shadow-sm p-6">
              <h3 className="text-sm font-medium text-gray-900 mb-4">Scoring System</h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
                <div className="flex items-center space-x-3">
                  <span className={getActionBadgeClasses('BUY')}>BUY</span>
                  <span className="text-gray-600">Score &gt; 80%</span>
                </div>
                <div className="flex items-center space-x-3">
                  <span className={getActionBadgeClasses('HOLD')}>HOLD</span>
                  <span className="text-gray-600">Score 50% - 80%</span>
                </div>
                <div className="flex items-center space-x-3">
                  <span className={getActionBadgeClasses('SELL')}>SELL</span>
                  <span className="text-gray-600">Score &lt; 50%</span>
                </div>
              </div>
              <p className="mt-4 text-xs text-gray-500">
                Recommendations are generated every 2 hours using news sentiment analysis 
                and technical indicators. The system keeps the last 10 recommendations 
                for each stock symbol.
              </p>
            </div>
          </div>
        )}
      </main>
      
      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-sm text-gray-500">
            AutoTrader AI - AI-powered trading recommendations for informed decision making.
            <br />
            <span className="text-xs">
              Disclaimer: These recommendations are for informational purposes only and 
              do not constitute financial advice.
            </span>
          </p>
        </div>
      </footer>
    </div>
  )
}
