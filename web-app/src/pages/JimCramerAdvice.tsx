/**
 * JimCramerAdvice.tsx - Jim Cramer Daily Advice Page
 * 
 * Displays Jim Cramer's latest stock recommendations and market views:
 * - Daily summary with market sentiment
 * - Top bullish and bearish picks
 * - Individual article summaries
 * - Stock mention trends
 * 
 * Data is fetched from the Jim Cramer service which crawls news daily at 9 AM PST.
 */

import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import Header from '../components/Header'

// Types for Jim Cramer data
interface StockPick {
  symbol: string
  reasoning: string
}

interface StockMention {
  symbol: string
  company_name: string | null
  sentiment: string
  sentiment_score: number
  recommendation: string | null
  reasoning: string | null
  article_title: string
  article_url: string
  published_at: string
}

interface DailySummary {
  id: number
  summary_date: string
  market_sentiment: string
  market_sentiment_score: number
  summary_title: string
  summary_text: string
  key_points: string[]
  top_bullish_picks: StockPick[]
  top_bearish_picks: StockPick[]
  stocks_to_watch: StockPick[]
  sectors_bullish: string[]
  sectors_bearish: string[]
  total_articles_analyzed: number
  total_stocks_mentioned: number
  generated_at: string
}

interface Article {
  id: number
  title: string
  article_url: string
  source_name: string
  published_at: string
  description: string | null
}

// API functions - use public URL for direct browser requests
const API_BASE = import.meta.env.VITE_PUBLIC_API_URL || import.meta.env.VITE_API_URL || 'http://localhost:3001'

async function fetchLatestSummary(): Promise<DailySummary | null> {
  try {
    const response = await fetch(`${API_BASE}/api/jim-cramer/summary/latest`)
    if (!response.ok) return null
    return await response.json()
  } catch (error) {
    console.error('Error fetching summary:', error)
    return null
  }
}

async function fetchTodayMentions(): Promise<StockMention[]> {
  try {
    const response = await fetch(`${API_BASE}/api/jim-cramer/mentions/today`)
    if (!response.ok) return []
    return await response.json()
  } catch (error) {
    console.error('Error fetching mentions:', error)
    return []
  }
}

async function fetchRecentArticles(): Promise<Article[]> {
  try {
    const response = await fetch(`${API_BASE}/api/jim-cramer/articles/recent?limit=10`)
    if (!response.ok) return []
    return await response.json()
  } catch (error) {
    console.error('Error fetching articles:', error)
    return []
  }
}

// Sentiment badge component
function SentimentBadge({ sentiment, score }: { sentiment: string; score?: number }) {
  const colors: Record<string, string> = {
    bullish: 'bg-green-100 text-green-800',
    bearish: 'bg-red-100 text-red-800',
    neutral: 'bg-gray-100 text-gray-800',
    mixed: 'bg-yellow-100 text-yellow-800',
  }
  
  const icons: Record<string, string> = {
    bullish: '📈',
    bearish: '📉',
    neutral: '➡️',
    mixed: '↔️',
  }
  
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-sm font-medium ${colors[sentiment] || colors.neutral}`}>
      {icons[sentiment] || '•'} {sentiment.charAt(0).toUpperCase() + sentiment.slice(1)}
      {score !== undefined && <span className="text-xs opacity-75">({(score * 100).toFixed(0)}%)</span>}
    </span>
  )
}

// Stock pick card component
function StockPickCard({ pick, type }: { pick: StockPick; type: 'bullish' | 'bearish' | 'watch' }) {
  const colors = {
    bullish: 'border-green-200 bg-green-50',
    bearish: 'border-red-200 bg-red-50',
    watch: 'border-blue-200 bg-blue-50',
  }
  
  const icons = {
    bullish: '🟢',
    bearish: '🔴',
    watch: '👀',
  }
  
  return (
    <div className={`rounded-lg border p-4 ${colors[type]}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">{icons[type]}</span>
        <span className="text-lg font-bold text-gray-900">{pick.symbol}</span>
      </div>
      <p className="text-sm text-gray-700">{pick.reasoning}</p>
    </div>
  )
}

// Main component
export default function JimCramerAdvice() {
  const { isLoading: authLoading } = useAuth()
  const [summary, setSummary] = useState<DailySummary | null>(null)
  const [mentions, setMentions] = useState<StockMention[]>([])
  const [articles, setArticles] = useState<Article[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'summary' | 'mentions' | 'articles'>('summary')
  
  useEffect(() => {
    async function loadData() {
      setLoading(true)
      const [summaryData, mentionsData, articlesData] = await Promise.all([
        fetchLatestSummary(),
        fetchTodayMentions(),
        fetchRecentArticles(),
      ])
      setSummary(summaryData)
      setMentions(mentionsData)
      setArticles(articlesData)
      setLoading(false)
    }
    
    // Load data regardless of authentication - this is public informational content
    loadData()
  }, [])
  
  if (authLoading && loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }
  
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Page Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-4xl">📺</span>
            <h1 className="text-3xl font-bold text-gray-900">Jim Cramer Advice</h1>
          </div>
          <p className="text-gray-600">
            AI-powered analysis of Jim Cramer's daily stock recommendations from CNBC Mad Money and Investing Club.
            Updated daily at 9:00 AM PST.
          </p>
        </div>
        
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-500">Loading Jim Cramer's latest advice...</p>
            </div>
          </div>
        ) : !summary ? (
          <div className="bg-white rounded-xl shadow-sm border p-8 text-center">
            <span className="text-6xl mb-4 block">📭</span>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">No Data Available Yet</h2>
            <p className="text-gray-500">
              The Jim Cramer service hasn't run yet or no articles were found today.
              Check back after 9:00 AM PST.
            </p>
          </div>
        ) : (
          <>
            {/* Daily Summary Card */}
            <div className="bg-white rounded-xl shadow-sm border overflow-hidden mb-6">
              {/* Summary Header */}
              <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-blue-100 text-sm">
                      {/* Parse date as UTC to avoid timezone offset issues */}
                      {new Date(summary.summary_date + (summary.summary_date.includes('T') ? '' : 'T12:00:00Z')).toLocaleDateString('en-US', {
                        weekday: 'long',
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        timeZone: 'UTC',
                      })}
                    </p>
                    <h2 className="text-xl font-bold text-white mt-1">{summary.summary_title}</h2>
                  </div>
                  <div className="text-right">
                    <SentimentBadge sentiment={summary.market_sentiment} score={summary.market_sentiment_score} />
                    <p className="text-blue-100 text-xs mt-2">
                      {summary.total_articles_analyzed} articles • {summary.total_stocks_mentioned} stocks
                    </p>
                  </div>
                </div>
              </div>
              
              {/* Summary Content */}
              <div className="p-6">
                <p className="text-gray-700 leading-relaxed mb-6">{summary.summary_text}</p>
                
                {/* Key Points */}
                {summary.key_points && summary.key_points.length > 0 && (
                  <div className="mb-6">
                    <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                      Key Takeaways
                    </h3>
                    <ul className="space-y-2">
                      {summary.key_points.map((point, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-blue-500 mt-0.5">•</span>
                          <span className="text-gray-700">{point}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {/* Sectors */}
                <div className="flex gap-6 text-sm">
                  {summary.sectors_bullish && summary.sectors_bullish.length > 0 && (
                    <div>
                      <span className="text-gray-500">Bullish Sectors:</span>{' '}
                      <span className="text-green-700 font-medium">
                        {summary.sectors_bullish.join(', ')}
                      </span>
                    </div>
                  )}
                  {summary.sectors_bearish && summary.sectors_bearish.length > 0 && (
                    <div>
                      <span className="text-gray-500">Bearish Sectors:</span>{' '}
                      <span className="text-red-700 font-medium">
                        {summary.sectors_bearish.join(', ')}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
            
            {/* Stock Picks Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              {/* Bullish Picks */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <span className="text-green-500">📈</span> Top Bullish Picks
                </h3>
                <div className="space-y-3">
                  {summary.top_bullish_picks && summary.top_bullish_picks.length > 0 ? (
                    summary.top_bullish_picks.map((pick, idx) => (
                      <StockPickCard key={idx} pick={pick} type="bullish" />
                    ))
                  ) : (
                    <p className="text-gray-500 text-sm">No bullish picks today</p>
                  )}
                </div>
              </div>
              
              {/* Bearish Picks */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <span className="text-red-500">📉</span> Top Bearish Picks
                </h3>
                <div className="space-y-3">
                  {summary.top_bearish_picks && summary.top_bearish_picks.length > 0 ? (
                    summary.top_bearish_picks.map((pick, idx) => (
                      <StockPickCard key={idx} pick={pick} type="bearish" />
                    ))
                  ) : (
                    <p className="text-gray-500 text-sm">No bearish picks today</p>
                  )}
                </div>
              </div>
              
              {/* Stocks to Watch */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <span>👀</span> Stocks to Watch
                </h3>
                <div className="space-y-3">
                  {summary.stocks_to_watch && summary.stocks_to_watch.length > 0 ? (
                    summary.stocks_to_watch.map((pick, idx) => (
                      <StockPickCard key={idx} pick={pick} type="watch" />
                    ))
                  ) : (
                    <p className="text-gray-500 text-sm">No stocks to watch today</p>
                  )}
                </div>
              </div>
            </div>
            
            {/* Tabs for Mentions and Articles */}
            <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
              {/* Tab Headers */}
              <div className="border-b">
                <nav className="flex">
                  <button
                    onClick={() => setActiveTab('mentions')}
                    className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === 'mentions'
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    Stock Mentions ({mentions.length})
                  </button>
                  <button
                    onClick={() => setActiveTab('articles')}
                    className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === 'articles'
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    Recent Articles ({articles.length})
                  </button>
                </nav>
              </div>
              
              {/* Tab Content */}
              <div className="p-6">
                {activeTab === 'mentions' && (
                  <div className="space-y-4">
                    {mentions.length > 0 ? (
                      mentions.map((mention, idx) => (
                        <div key={idx} className="flex items-start gap-4 p-4 bg-gray-50 rounded-lg">
                          <div className="flex-shrink-0">
                            <span className="inline-block px-3 py-1 bg-white border rounded font-bold text-gray-900">
                              {mention.symbol}
                            </span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <SentimentBadge sentiment={mention.sentiment} score={mention.sentiment_score} />
                              {mention.recommendation && (
                                <span className="text-sm text-gray-500">
                                  Recommendation: <span className="font-medium">{mention.recommendation}</span>
                                </span>
                              )}
                            </div>
                            {mention.reasoning && (
                              <p className="text-sm text-gray-700 mb-2">{mention.reasoning}</p>
                            )}
                            <a
                              href={mention.article_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-blue-600 hover:underline"
                            >
                              {mention.article_title}
                            </a>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="text-gray-500 text-center py-8">No stock mentions today</p>
                    )}
                  </div>
                )}
                
                {activeTab === 'articles' && (
                  <div className="space-y-4">
                    {articles.length > 0 ? (
                      articles.map((article) => (
                        <a
                          key={article.id}
                          href={article.article_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div>
                              <h4 className="font-medium text-gray-900 hover:text-blue-600">
                                {article.title}
                              </h4>
                              {article.description && (
                                <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                                  {article.description}
                                </p>
                              )}
                            </div>
                            <div className="flex-shrink-0 text-right">
                              <span className="text-xs text-gray-500">{article.source_name}</span>
                              <p className="text-xs text-gray-400">
                                {new Date(article.published_at).toLocaleDateString('en-US', { timeZone: 'UTC' })}
                              </p>
                            </div>
                          </div>
                        </a>
                      ))
                    ) : (
                      <p className="text-gray-500 text-center py-8">No articles found</p>
                    )}
                  </div>
                )}
              </div>
            </div>
            
            {/* Last Updated */}
            <p className="text-center text-sm text-gray-400 mt-6">
              Last updated: {new Date(summary.generated_at).toLocaleString('en-US', { timeZone: 'UTC' })} UTC
            </p>
          </>
        )}
      </main>
    </div>
  )
}
