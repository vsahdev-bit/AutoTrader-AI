import { useState, useEffect } from 'react'
import { 
  ArrowTrendingDownIcon, 
  ExclamationTriangleIcon, 
  CurrencyDollarIcon, 
  ChartBarIcon, 
  ArrowPathIcon, 
  ClockIcon,
  BellIcon,
  BellSlashIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline'
import Header from '../components/Header'
import RegimeDisplay from '../components/RegimeDisplay'
import type { RegimeResponse } from '../types'

// Types
interface BigCapLoser {
  id: number
  loser_id?: number
  symbol: string
  company_name: string
  current_price: string
  price_change: string
  percent_change: string
  market_cap: string
  market_cap_formatted: string
  volume: string
  trading_date: string
  crawled_at: string
  // Recommendation fields
  recommendation_id?: string
  action?: 'BUY' | 'SELL' | 'HOLD'
  score?: number
  normalized_score?: number
  confidence?: number
  market_regime?: string
  regime_confidence?: number
  news_score?: number
  technical_score?: number
  explanation?: any
  recommendation_generated_at?: string
}

interface ExplanationData {
  action?: string
  summary?: string
  reasoning?: string
  key_factors?: string[]
  risk_factors?: string[]
  news_summary?: string
  technical_summary?: string
}

interface DailySummary {
  summary_date: string
  total_stocks_tracked: number
  stocks_over_15_percent_drop: number
  worst_performer_symbol: string
  worst_performer_drop: string
  top_losers: Array<{
    symbol: string
    company_name: string
    percent_change: number
    market_cap_formatted: string
  }>
}

// API functions
const API_BASE = import.meta.env.VITE_PUBLIC_API_URL || import.meta.env.VITE_API_URL || 'http://localhost:3001'

async function fetchLatestLosers(): Promise<BigCapLoser[]> {
  try {
    // Use the endpoint that includes recommendations
    const response = await fetch(`${API_BASE}/api/big-cap-losers/with-recommendations`)
    if (!response.ok) {
      // Fallback to basic endpoint
      const fallbackResponse = await fetch(`${API_BASE}/api/big-cap-losers/latest`)
      if (!fallbackResponse.ok) return []
      return await fallbackResponse.json()
    }
    return await response.json()
  } catch (error) {
    console.error('Error fetching latest losers:', error)
    return []
  }
}

async function fetchOver10Losers(): Promise<BigCapLoser[]> {
  try {
    // Fetch with recommendations and filter for over 10%
    const response = await fetch(`${API_BASE}/api/big-cap-losers/with-recommendations`)
    if (!response.ok) {
      const fallbackResponse = await fetch(`${API_BASE}/api/big-cap-losers/over-10`)
      if (!fallbackResponse.ok) return []
      return await fallbackResponse.json()
    }
    const data = await response.json()
    return data.filter((l: BigCapLoser) => parseFloat(l.percent_change) <= -10)
  } catch (error) {
    console.error('Error fetching over 10% losers:', error)
    return []
  }
}

async function fetchSummary(): Promise<DailySummary | null> {
  try {
    const response = await fetch(`${API_BASE}/api/big-cap-losers/summary`)
    if (!response.ok) return null
    return await response.json()
  } catch (error) {
    console.error('Error fetching summary:', error)
    return null
  }
}

async function generateRecommendations(): Promise<{ success: boolean; generated: number }> {
  try {
    const response = await fetch(`${API_BASE}/api/big-cap-losers/generate-recommendations`, {
      method: 'POST'
    })
    if (!response.ok) return { success: false, generated: 0 }
    return await response.json()
  } catch (error) {
    console.error('Error generating recommendations:', error)
    return { success: false, generated: 0 }
  }
}

async function fetchRegimeData(symbol: string): Promise<RegimeResponse | null> {
  try {
    // Uses Vite proxy: /regime -> http://localhost:8000
    const response = await fetch(`/regime/${symbol}`)
    if (!response.ok) return null
    return await response.json()
  } catch (error) {
    console.error('Error fetching regime data:', error)
    return null
  }
}

// Helper functions
function formatNumber(num: string | number): string {
  const n = typeof num === 'string' ? parseFloat(num) : num
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatVolume(vol: string | number): string {
  const n = typeof vol === 'string' ? parseFloat(vol) : vol
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}

function getPercentColor(percent: number): string {
  if (percent <= -10) return 'text-red-600 bg-red-100'
  if (percent <= -5) return 'text-red-500 bg-red-50'
  if (percent <= -3) return 'text-orange-500 bg-orange-50'
  return 'text-yellow-600 bg-yellow-50'
}

// Loading Skeleton Components
function SkeletonStatCard() {
  return (
    <div className="bg-white rounded-xl shadow-sm border p-6 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="h-4 w-24 bg-gray-200 rounded"></div>
          <div className="h-8 w-16 bg-gray-300 rounded"></div>
        </div>
        <div className="w-10 h-10 bg-gray-200 rounded"></div>
      </div>
    </div>
  )
}

function SkeletonTableRow() {
  return (
    <tr className="border-b animate-pulse">
      <td className="px-3 py-3 text-center">
        <div className="w-7 h-7 bg-gray-200 rounded-full mx-auto"></div>
      </td>
      <td className="px-3 py-3">
        <div className="flex items-center gap-2">
          <div className="space-y-2">
            <div className="h-4 w-14 bg-gray-300 rounded"></div>
            <div className="h-3 w-24 bg-gray-200 rounded"></div>
          </div>
        </div>
      </td>
      <td className="px-3 py-3 text-right">
        <div className="space-y-2 flex flex-col items-end">
          <div className="h-4 w-16 bg-gray-300 rounded"></div>
          <div className="h-3 w-12 bg-gray-200 rounded"></div>
        </div>
      </td>
      <td className="px-3 py-3 text-center">
        <div className="h-5 w-16 bg-gray-200 rounded-full mx-auto"></div>
      </td>
      <td className="px-3 py-3 text-right">
        <div className="h-4 w-14 bg-gray-200 rounded ml-auto"></div>
      </td>
      {/* Recommendation columns */}
      <td className="px-3 py-3 text-center bg-blue-50/50">
        <div className="h-5 w-12 bg-gray-200 rounded-full mx-auto"></div>
      </td>
      <td className="px-3 py-3 text-center bg-blue-50/50">
        <div className="h-4 w-10 bg-gray-200 rounded mx-auto"></div>
      </td>
      <td className="px-3 py-3 text-center bg-blue-50/50">
        <div className="h-4 w-16 bg-gray-200 rounded mx-auto"></div>
      </td>
      <td className="px-3 py-3 text-center bg-blue-50/50">
        <div className="h-5 w-14 bg-gray-200 rounded mx-auto"></div>
      </td>
      <td className="px-3 py-3 text-center bg-blue-50/50">
        <div className="h-4 w-10 bg-gray-200 rounded mx-auto"></div>
      </td>
    </tr>
  )
}

function LoadingSkeleton() {
  return (
    <>
      {/* Stats Cards Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <SkeletonStatCard />
        <SkeletonStatCard />
        <SkeletonStatCard />
        <SkeletonStatCard />
      </div>
      
      {/* Table Skeleton */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1000px]">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600">Rank</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-gray-600">Stock</th>
                <th className="px-3 py-3 text-right text-xs font-semibold text-gray-600">Price</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600">Change %</th>
                <th className="px-3 py-3 text-right text-xs font-semibold text-gray-600">Market Cap</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 bg-blue-50">Action</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 bg-blue-50">Score</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 bg-blue-50">Confidence</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 bg-blue-50">Regime</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 bg-blue-50">Top News</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 bg-blue-50">Details</th>
              </tr>
            </thead>
            <tbody>
              {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                <SkeletonTableRow key={i} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

// Notification/Sound helper
function playAlertSound() {
  try {
    // Create an audio context for the alert sound
    const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
    
    // Create oscillator for alert beep
    const oscillator = audioContext.createOscillator()
    const gainNode = audioContext.createGain()
    
    oscillator.connect(gainNode)
    gainNode.connect(audioContext.destination)
    
    // Alert sound - two quick beeps
    oscillator.frequency.value = 800
    oscillator.type = 'sine'
    gainNode.gain.value = 0.3
    
    oscillator.start()
    
    // First beep
    setTimeout(() => {
      gainNode.gain.value = 0
    }, 150)
    
    // Second beep
    setTimeout(() => {
      gainNode.gain.value = 0.3
    }, 200)
    
    setTimeout(() => {
      oscillator.stop()
      audioContext.close()
    }, 350)
  } catch (e) {
    console.log('Audio not supported')
  }
}

function showBrowserNotification(title: string, body: string) {
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification(title, {
      body,
      icon: '📉',
      tag: 'big-cap-losers-alert'
    })
  }
}

// Action badge component
function ActionBadge({ action }: { action?: string }) {
  if (!action) return <span className="text-gray-400 text-sm">-</span>
  
  const colors = {
    BUY: 'bg-green-100 text-green-800 border-green-200',
    SELL: 'bg-red-100 text-red-800 border-red-200',
    HOLD: 'bg-yellow-100 text-yellow-800 border-yellow-200'
  }
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border ${colors[action as keyof typeof colors] || 'bg-gray-100 text-gray-800'}`}>
      {action}
    </span>
  )
}

// Confidence bar component
function ConfidenceBar({ value, label }: { value?: number; label?: string }) {
  if (value === undefined || value === null) return <span className="text-gray-400 text-sm">-</span>
  
  const percentage = Math.round(value * 100)
  const color = percentage >= 70 ? 'bg-green-500' : percentage >= 50 ? 'bg-yellow-500' : 'bg-red-500'
  
  return (
    <div className="w-20">
      <div className="flex justify-between text-xs mb-1">
        <span className="font-medium">{percentage}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-1.5">
        <div className={`${color} h-1.5 rounded-full`} style={{ width: `${percentage}%` }}></div>
      </div>
    </div>
  )
}

// Top News Modal
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

// Explanation Modal Component - matches quality of recommendations page
function ExplanationModal({ 
  isOpen, 
  onClose, 
  loser,
  regimeData
}: { 
  isOpen: boolean
  onClose: () => void
  loser: BigCapLoser | null
  regimeData?: RegimeResponse
}) {
  if (!isOpen || !loser) return null
  
  const explanation = loser.explanation || {}
  const regime = regimeData?.regime
  const confidence = regimeData?.signal_weights?.confidence_multiplier || loser.confidence
  
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:p-0">
        {/* Backdrop */}
        <div 
          className="fixed inset-0 transition-opacity bg-gray-500 bg-opacity-75" 
          onClick={onClose}
        />
        
        {/* Modal */}
        <div className="relative inline-block w-full max-w-2xl p-6 my-8 overflow-hidden text-left align-middle transition-all transform bg-white shadow-xl rounded-2xl max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="flex items-center gap-3">
                <h3 className="text-xl font-bold text-gray-900">{loser.symbol}</h3>
                {loser.action && (
                  <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-bold ${
                    loser.action === 'BUY' ? 'bg-green-100 text-green-800' :
                    loser.action === 'SELL' ? 'bg-red-100 text-red-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {loser.action}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 mt-1">{loser.company_name}</p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors p-2 hover:bg-gray-100 rounded-full"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          {/* Price & Change Banner */}
          <div className="mb-6 p-4 bg-gradient-to-r from-red-50 to-orange-50 rounded-xl border border-red-100">
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide">Price</p>
                <p className="text-lg font-bold text-gray-900">${parseFloat(loser.current_price).toFixed(2)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide">Change</p>
                <p className="text-lg font-bold text-red-600">{parseFloat(loser.percent_change).toFixed(2)}%</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide">Market Cap</p>
                <p className="text-lg font-bold text-gray-900">{loser.market_cap_formatted}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide">Volume</p>
                <p className="text-lg font-bold text-gray-900">{loser.volume ? formatVolume(loser.volume) : '-'}</p>
              </div>
            </div>
          </div>
          
          {/* Scores Grid */}
          <div className="mb-6 grid grid-cols-3 gap-4">
            <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
              <p className="text-xs text-blue-600 uppercase tracking-wide mb-1">AI Score</p>
              <p className="text-2xl font-bold text-blue-900">
                {loser.normalized_score ? (loser.normalized_score * 100).toFixed(0) : '-'}%
              </p>
              <div className="mt-2 w-full bg-blue-200 rounded-full h-2">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all"
                  style={{ width: `${(loser.normalized_score || 0) * 100}%` }}
                />
              </div>
            </div>
            <div className="p-4 bg-purple-50 rounded-xl border border-purple-100">
              <p className="text-xs text-purple-600 uppercase tracking-wide mb-1">Confidence</p>
              <p className="text-2xl font-bold text-purple-900">
                {confidence ? (confidence * 100).toFixed(0) : '-'}%
              </p>
              <div className="mt-2 w-full bg-purple-200 rounded-full h-2">
                <div 
                  className="bg-purple-600 h-2 rounded-full transition-all"
                  style={{ width: `${(confidence || 0) * 100}%` }}
                />
              </div>
            </div>
            <div className="p-4 bg-indigo-50 rounded-xl border border-indigo-100">
              <p className="text-xs text-indigo-600 uppercase tracking-wide mb-1">Market Regime</p>
              <p className="text-lg font-bold text-indigo-900 capitalize truncate">
                {regime?.label || loser.market_regime || '-'}
              </p>
              {regime?.volatility && (
                <p className="text-xs text-indigo-600 mt-1">Vol: {regime.volatility}</p>
              )}
            </div>
          </div>
          
          {/* Regime Details (if available) */}
          {regime && (
            <div className="mb-6 p-4 bg-gray-50 rounded-xl border">
              <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <ChartBarIcon className="w-5 h-5 text-indigo-600" />
                Market Analysis
              </h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                {regime.trend && (
                  <div>
                    <span className="text-gray-500">Trend:</span>
                    <span className="ml-2 font-medium capitalize">{regime.trend}</span>
                  </div>
                )}
                {regime.volatility && (
                  <div>
                    <span className="text-gray-500">Volatility:</span>
                    <span className="ml-2 font-medium capitalize">{regime.volatility}</span>
                  </div>
                )}
                {regime.risk_score !== undefined && (
                  <div>
                    <span className="text-gray-500">Risk Score:</span>
                    <span className="ml-2 font-medium">{(regime.risk_score * 100).toFixed(0)}%</span>
                  </div>
                )}
                {regime.recommendation && (
                  <div className="col-span-2">
                    <span className="text-gray-500">Regime Recommendation:</span>
                    <span className="ml-2 font-medium">{regime.recommendation}</span>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Explanation Content */}
          <div className="space-y-4">
            {explanation.summary && (
              <div className="p-4 bg-white rounded-xl border">
                <h4 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                  <InformationCircleIcon className="w-5 h-5 text-blue-600" />
                  Summary
                </h4>
                <p className="text-gray-700">{explanation.summary}</p>
              </div>
            )}
            
            {explanation.reasoning && (
              <div className="p-4 bg-white rounded-xl border">
                <h4 className="font-semibold text-gray-900 mb-2">Analysis</h4>
                <p className="text-gray-700">{explanation.reasoning}</p>
              </div>
            )}
            
            <div className="grid grid-cols-2 gap-4">
              {explanation.key_factors && explanation.key_factors.length > 0 && (
                <div className="p-4 bg-green-50 rounded-xl border border-green-100">
                  <h4 className="font-semibold text-green-900 mb-2">Key Factors</h4>
                  <ul className="space-y-2">
                    {explanation.key_factors.map((factor: string, i: number) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-green-800">
                        <span className="text-green-500 mt-0.5">✓</span>
                        {factor}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              {explanation.risk_factors && explanation.risk_factors.length > 0 && (
                <div className="p-4 bg-red-50 rounded-xl border border-red-100">
                  <h4 className="font-semibold text-red-900 mb-2">Risk Factors</h4>
                  <ul className="space-y-2">
                    {explanation.risk_factors.map((factor: string, i: number) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-red-800">
                        <span className="text-red-500 mt-0.5">⚠</span>
                        {factor}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            
            {!explanation.summary && !explanation.reasoning && (
              <div className="p-4 bg-gray-50 rounded-xl border text-center">
                <p className="text-gray-500">No detailed explanation available yet.</p>
                <p className="text-gray-400 text-sm mt-1">Recommendations are generated hourly with the market data.</p>
              </div>
            )}
          </div>
          
          {/* Footer */}
          <div className="mt-6 pt-4 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
            <span>
              {loser.recommendation_generated_at 
                ? `Generated: ${new Date(loser.recommendation_generated_at).toLocaleString('en-US', { timeZone: 'UTC' })} UTC`
                : 'Recommendation pending'}
            </span>
            <span className="text-gray-400">
              Data sources: {loser.news_score ? 'News, ' : ''}{loser.technical_score ? 'Technical, ' : ''}Price
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

// Components
function StatCard({ title, value, icon: Icon, color }: { 
  title: string
  value: string | number
  icon: React.ElementType
  color: string 
}) {
  return (
    <div className={`bg-white rounded-xl shadow-sm border p-6 ${color}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
        </div>
        <Icon className="w-10 h-10 text-gray-300" />
      </div>
    </div>
  )
}

function LoserRow({ 
  loser, 
  rank, 
  onExplanationClick,
  onTopNewsClick,
  onRegimeClick,
  regimeData
}: { 
  loser: BigCapLoser
  rank: number
  onExplanationClick: (loser: BigCapLoser) => void
  onTopNewsClick: (symbol: string, articles: any[]) => void
  onRegimeClick: (symbol: string) => void
  regimeData?: RegimeResponse | null
}) {
  const percentChange = parseFloat(loser.percent_change)
  const isOver10 = percentChange <= -10
  
  return (
    <tr className={`border-b hover:bg-gray-50 ${isOver10 ? 'bg-red-50' : ''}`}>
      <td className="px-3 py-3 text-center">
        <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-sm font-bold ${
          rank <= 3 ? 'bg-red-600 text-white' : 'bg-gray-200 text-gray-700'
        }`}>
          {rank}
        </span>
      </td>
      <td className="px-3 py-3">
        <div className="flex items-center gap-2">
          {isOver10 && <ExclamationTriangleIcon className="w-4 h-4 text-red-500 animate-pulse flex-shrink-0" />}
          <div>
            <p className="font-bold">{loser.symbol}</p>
            <p className="text-xs text-gray-500 truncate max-w-[150px]">{loser.company_name}</p>
          </div>
        </div>
      </td>
      <td className="px-3 py-3 text-right">
        <p className="font-semibold">${formatNumber(loser.current_price)}</p>
        <p className="text-xs text-red-500">{parseFloat(loser.price_change) > 0 ? '+' : ''}{formatNumber(loser.price_change)}</p>
      </td>
      <td className="px-3 py-3 text-center">
        <span className={`inline-block px-2 py-0.5 rounded-full text-sm font-bold ${getPercentColor(percentChange)}`}>
          {percentChange > 0 ? '+' : ''}{formatNumber(percentChange)}%
        </span>
      </td>
      <td className="px-3 py-3 text-right text-sm font-medium">{loser.market_cap_formatted}</td>
      {/* Recommendation columns */}
      <td className="px-3 py-3 text-center">
        <ActionBadge action={loser.action} />
      </td>
      <td className="px-3 py-3 text-center">
        {loser.normalized_score !== undefined && loser.normalized_score !== null ? (
          <span className="font-medium">{(loser.normalized_score * 100).toFixed(0)}%</span>
        ) : (
          <span className="text-gray-400 text-sm">-</span>
        )}
      </td>
      <td className="px-3 py-3 text-center">
        <ConfidenceBar value={regimeData?.signal_weights?.confidence_multiplier || loser.confidence} />
      </td>
      <td className="px-3 py-3 text-center">
        {(regimeData?.regime?.label || loser.market_regime) ? (
          <button
            onClick={() => onRegimeClick(loser.symbol)}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800 hover:bg-purple-200 transition-colors cursor-pointer"
          >
            <span className="capitalize truncate max-w-[100px]">{regimeData?.regime?.label || loser.market_regime}</span>
            <InformationCircleIcon className="w-3 h-3 flex-shrink-0" />
          </button>
        ) : (
          <span className="text-gray-400 text-sm">-</span>
        )}
      </td>
      <td className="px-3 py-3 text-center">
        {(() => {
          let explanation: any = loser.explanation
          if (typeof explanation === 'string') {
            try { explanation = JSON.parse(explanation) } catch { explanation = null }
          }
          const articles = explanation?.recent_articles || []
          const hasArticles = Array.isArray(articles) && articles.length > 0

          return hasArticles ? (
            <button
              onClick={() => onTopNewsClick(loser.symbol, articles)}
              className="text-blue-600 hover:text-blue-800 hover:underline text-sm font-medium"
              title="View top news used in analysis"
            >
              View ({articles.length})
            </button>
          ) : (
            <span className="text-gray-400 text-sm">-</span>
          )
        })()}
      </td>
      <td className="px-3 py-3 text-center">
        {loser.recommendation_id ? (
          <button
            onClick={() => onExplanationClick(loser)}
            className="text-blue-600 hover:text-blue-800 hover:underline text-sm font-medium"
          >
            View
          </button>
        ) : (
          <span className="text-gray-400 text-sm">-</span>
        )}
      </td>
    </tr>
  )
}

// Main component
export default function BigCapLosers() {
  const [allLosers, setAllLosers] = useState<BigCapLoser[]>([])
  const [over10Losers, setOver10Losers] = useState<BigCapLoser[]>([])
  const [summary, setSummary] = useState<DailySummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'all' | 'over10'>('over10')
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [notificationsEnabled, setNotificationsEnabled] = useState(false)
  const [prevOver10Count, setPrevOver10Count] = useState<number>(0)
  const [selectedLoser, setSelectedLoser] = useState<BigCapLoser | null>(null)
  const [isExplanationModalOpen, setIsExplanationModalOpen] = useState(false)
  const [isTopNewsModalOpen, setIsTopNewsModalOpen] = useState(false)
  const [topNewsSymbol, setTopNewsSymbol] = useState<string | null>(null)
  const [topNewsArticles, setTopNewsArticles] = useState<any[]>([])
  const [isGeneratingRecs, setIsGeneratingRecs] = useState(false)
  const [regimeData, setRegimeData] = useState<Record<string, RegimeResponse>>({})
  const [selectedRegimeSymbol, setSelectedRegimeSymbol] = useState<string | null>(null)

  // Request notification permission on mount
  useEffect(() => {
    if ('Notification' in window) {
      if (Notification.permission === 'granted') {
        setNotificationsEnabled(true)
      } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(permission => {
          setNotificationsEnabled(permission === 'granted')
        })
      }
    }
  }, [])

  // Check for new significant drops and trigger alerts
  const checkForAlerts = (newOver10: BigCapLoser[], previousCount: number) => {
    // Only alert if notifications are enabled
    if (!notificationsEnabled) return
    
    if (newOver10.length > previousCount && previousCount > 0) {
      // New stocks have fallen over 10%
      const newDrops = newOver10.length - previousCount
      const symbols = newOver10.slice(0, newDrops).map(l => l.symbol).join(', ')
      
      // Play alert sound
      playAlertSound()
      
      // Show browser notification
      showBrowserNotification(
        `🚨 ${newDrops} New Big Cap Loser${newDrops > 1 ? 's' : ''}!`,
        `${symbols} ${newDrops > 1 ? 'have' : 'has'} fallen over 10%`
      )
    } else if (newOver10.length > 0 && previousCount === 0) {
      // First load with drops - play alert
      playAlertSound()
      showBrowserNotification(
        `🚨 ${newOver10.length} Big Cap Stock${newOver10.length > 1 ? 's' : ''} Down Over 10%!`,
        `${newOver10.map(l => l.symbol).join(', ')}`
      )
    }
  }

  const loadData = async () => {
    setLoading(true)
    const [losersData, over10Data, summaryData] = await Promise.all([
      fetchLatestLosers(),
      fetchOver10Losers(),
      fetchSummary(),
    ])
    
    // Check for alerts before updating state
    checkForAlerts(over10Data, prevOver10Count)
    
    setAllLosers(losersData)
    setOver10Losers(over10Data)
    setPrevOver10Count(over10Data.length)
    setSummary(summaryData)
    setLastUpdated(new Date())
    setLoading(false)
    
    // Fetch regime data for all stocks in background
    const uniqueSymbols = [...new Set(losersData.map(l => l.symbol))]
    for (const symbol of uniqueSymbols) {
      if (!regimeData[symbol]) {
        fetchRegimeData(symbol).then(data => {
          if (data) {
            setRegimeData(prev => ({ ...prev, [symbol]: data }))
          }
        })
      }
    }
  }

  const [isRefreshing, setIsRefreshing] = useState(false)
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null)

  const handleRefresh = async () => {
    try {
      setIsRefreshing(true)
      setRefreshMessage('🔄 Step 1/3: Crawling Yahoo Finance for latest stock data...')
      
      // Step 1: Trigger the crawler service to fetch fresh data AND generate recommendations
      // The backend handles both crawling and recommendation generation in one call
      const response = await fetch(`${API_BASE}/api/big-cap-losers/refresh`, {
        method: 'POST'
      })
      
      if (!response.ok) {
        throw new Error('Refresh failed')
      }
      
      const refreshResult = await response.json()
      
      if (refreshResult.success) {
        const stats = refreshResult.stats || {}
        
        // Show what was done by the crawler
        setRefreshMessage(`🔄 Step 2/3: Crawled ${stats.big_cap_losers || 0} stocks, generated ${stats.recommendations_generated || 0} recommendations. Loading data...`)
        
        // Step 2: Wait a moment for DB to fully update
        await new Promise(resolve => setTimeout(resolve, 500))
        
        // Step 3: Reload data using the proper endpoints that include recommendations
        setRefreshMessage('🔄 Step 3/3: Loading updated data with recommendations...')
        
        const [losersData, over10Data, summaryData] = await Promise.all([
          fetchLatestLosers(),
          fetchOver10Losers(),
          fetchSummary(),
        ])
        
        // Check for alerts
        checkForAlerts(over10Data, prevOver10Count)
        
        setAllLosers(losersData)
        setOver10Losers(over10Data)
        setPrevOver10Count(over10Data.length)
        setSummary(summaryData)
        setLastUpdated(new Date())
        
        // Show completion message with stats
        const recsCount = stats.recommendations_generated || losersData.filter(l => l.recommendation_id).length
        setRefreshMessage(`✓ Complete! Found ${losersData.length} losers (${over10Data.length} over 10%), ${recsCount} recommendations generated`)
        
        // Step 4: Fetch regime data for any new stocks in background
        const uniqueSymbols = [...new Set(losersData.map(l => l.symbol))]
        for (const symbol of uniqueSymbols) {
          if (!regimeData[symbol]) {
            fetchRegimeData(symbol).then(data => {
              if (data) {
                setRegimeData(prev => ({ ...prev, [symbol]: data }))
              }
            })
          }
        }
      } else {
        setRefreshMessage('❌ Crawler did not return success. Try again.')
      }
      
      setTimeout(() => setRefreshMessage(null), 5000)
    } catch (error) {
      console.error('Error refreshing data:', error)
      setRefreshMessage('❌ Failed to refresh. Try again.')
      setTimeout(() => setRefreshMessage(null), 3000)
    } finally {
      setIsRefreshing(false)
    }
  }

  const handleGenerateRecommendations = async () => {
    try {
      setIsGeneratingRecs(true)
      setRefreshMessage('Generating AI recommendations for all losers...')
      
      const result = await generateRecommendations()
      
      if (result.success) {
        setRefreshMessage(`✓ Generated recommendations for ${result.generated} stocks`)
        // Reload data to show new recommendations
        await loadData()
      } else {
        setRefreshMessage('Failed to generate recommendations')
      }
      
      setTimeout(() => setRefreshMessage(null), 5000)
    } catch (error) {
      console.error('Error generating recommendations:', error)
      setRefreshMessage('Failed to generate recommendations')
      setTimeout(() => setRefreshMessage(null), 3000)
    } finally {
      setIsGeneratingRecs(false)
    }
  }

  const handleExplanationClick = (loser: BigCapLoser) => {
    setSelectedLoser(loser)
    setIsExplanationModalOpen(true)
  }

  const handleTopNewsClick = (symbol: string, articles: any[]) => {
    setTopNewsSymbol(symbol)
    setTopNewsArticles(articles)
    setIsTopNewsModalOpen(true)
  }

  const handleRegimeClick = async (symbol: string) => {
    setSelectedRegimeSymbol(symbol)
    // Fetch regime data if not already cached
    if (!regimeData[symbol]) {
      const data = await fetchRegimeData(symbol)
      if (data) {
        setRegimeData(prev => ({ ...prev, [symbol]: data }))
      }
    }
  }

  const handleRegimeClose = () => {
    setSelectedRegimeSymbol(null)
  }

  useEffect(() => {
    loadData()
    
    // Auto-refresh every 5 minutes
    const interval = setInterval(loadData, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  const displayLosers = activeTab === 'over10' ? over10Losers : allLosers

  if (loading && allLosers.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="max-w-7xl mx-auto px-4 py-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-4">
              <div className="bg-red-600 p-3 rounded-xl">
                <ArrowTrendingDownIcon className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-gray-900">Big Cap Losers</h1>
                <p className="text-gray-500">Tracking large-cap stocks (&gt;$1B) with significant drops</p>
              </div>
            </div>
            <button
              disabled
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-100 text-gray-400 cursor-not-allowed"
            >
              <ArrowPathIcon className="w-4 h-4 animate-spin" />
              Loading...
            </button>
          </div>
          
          {/* Loading message */}
          <div className="mb-6 px-4 py-2 rounded-lg text-sm bg-blue-100 text-blue-700">
            Loading latest data...
          </div>
          
          {/* Skeleton */}
          <LoadingSkeleton />
          
          {/* Footer Info */}
          <div className="mt-8 text-center text-sm text-gray-500">
            <p>Data sourced from Yahoo Finance • Criteria: Market Cap &gt; $1B</p>
            <p>Service refreshes every 1 hour during market hours</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <div className="bg-red-600 p-3 rounded-xl">
              <ArrowTrendingDownIcon className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Big Cap Losers</h1>
              <p className="text-gray-500">Tracking large-cap stocks (&gt;$1B) with significant drops</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Notification Toggle */}
            <button
              onClick={() => {
                if (!notificationsEnabled && 'Notification' in window) {
                  Notification.requestPermission().then(permission => {
                    setNotificationsEnabled(permission === 'granted')
                    if (permission === 'granted') {
                      playAlertSound()
                    }
                  })
                } else {
                  setNotificationsEnabled(!notificationsEnabled)
                }
              }}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg transition ${
                notificationsEnabled
                  ? 'bg-green-100 text-green-700 border border-green-200'
                  : 'bg-gray-100 text-gray-500 border border-gray-200'
              }`}
              title={notificationsEnabled ? 'Notifications enabled' : 'Enable notifications'}
            >
              {notificationsEnabled ? (
                <BellIcon className="w-4 h-4" />
              ) : (
                <BellSlashIcon className="w-4 h-4" />
              )}
            </button>
            
            {/* Refresh Button */}
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition ${
                isRefreshing 
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                  : 'bg-white border hover:bg-gray-50 text-gray-700'
              }`}
            >
              <ArrowPathIcon className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              {isRefreshing ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Refresh Message */}
        {refreshMessage && (
          <div className={`mb-4 px-4 py-2 rounded-lg text-sm ${
            refreshMessage.startsWith('✓') 
              ? 'bg-green-100 text-green-700' 
              : refreshMessage.startsWith('Failed') 
                ? 'bg-red-100 text-red-700'
                : 'bg-blue-100 text-blue-700'
          }`}>
            {refreshMessage}
          </div>
        )}

        {/* Last Updated */}
        {lastUpdated && (
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
            <ClockIcon className="w-4 h-4" />
            Last updated: {lastUpdated.toLocaleTimeString()}
          </div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <StatCard
            title="Total Big Cap Losers"
            value={allLosers.length}
            icon={ChartBarIcon}
            color="border-l-4 border-l-blue-500"
          />
          <StatCard
            title="Over 10% Drop"
            value={over10Losers.length}
            icon={ExclamationTriangleIcon}
            color="border-l-4 border-l-red-500"
          />
          <StatCard
            title="Worst Performer"
            value={summary?.worst_performer_symbol || '-'}
            icon={ArrowTrendingDownIcon}
            color="border-l-4 border-l-orange-500"
          />
          <StatCard
            title="Biggest Drop"
            value={summary ? `${parseFloat(summary.worst_performer_drop).toFixed(2)}%` : '-'}
            icon={CurrencyDollarIcon}
            color="border-l-4 border-l-purple-500"
          />
        </div>

        {/* Alert Banner for Over 10% */}
        {over10Losers.length > 0 && (
          <div className="bg-red-600 text-white rounded-xl p-4 mb-8 flex items-center gap-4">
            <ExclamationTriangleIcon className="w-8 h-8 animate-pulse" />
            <div>
              <p className="font-bold text-lg">
                🚨 {over10Losers.length} Big Cap Stock{over10Losers.length > 1 ? 's' : ''} Down Over 10%!
              </p>
              <p className="opacity-90">
                {over10Losers.map(l => l.symbol).join(', ')} {over10Losers.length === 1 ? 'has' : 'have'} fallen more than 10% today
              </p>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setActiveTab('over10')}
            className={`px-6 py-3 rounded-lg font-medium transition ${
              activeTab === 'over10'
                ? 'bg-red-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-100'
            }`}
          >
            <span className="flex items-center gap-2">
              <ExclamationTriangleIcon className="w-4 h-4" />
              Over 10% Drop ({over10Losers.length})
            </span>
          </button>
          <button
            onClick={() => setActiveTab('all')}
            className={`px-6 py-3 rounded-lg font-medium transition ${
              activeTab === 'all'
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-100'
            }`}
          >
            <span className="flex items-center gap-2">
              <ArrowTrendingDownIcon className="w-4 h-4" />
              All Big Cap Losers ({allLosers.length})
            </span>
          </button>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          {displayLosers.length === 0 ? (
            <div className="p-12 text-center">
              <ArrowTrendingDownIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-gray-700 mb-2">
                {activeTab === 'over10' ? 'No Stocks Over 10% Drop' : 'No Big Cap Losers Found'}
              </h3>
              <p className="text-gray-500">
                {activeTab === 'over10' 
                  ? 'Good news! No large-cap stocks have fallen more than 10% today.'
                  : 'No data available yet. The crawler runs every 1 hour.'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1000px]">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600">Rank</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-600">Stock</th>
                    <th className="px-3 py-3 text-right text-xs font-semibold text-gray-600">Price</th>
                    <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600">Change %</th>
                    <th className="px-3 py-3 text-right text-xs font-semibold text-gray-600">Market Cap</th>
                    <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 bg-blue-50">Action</th>
                    <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 bg-blue-50">Score</th>
                    <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 bg-blue-50">Confidence</th>
                    <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 bg-blue-50">Regime</th>
                    <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 bg-blue-50">Top News</th>
                    <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 bg-blue-50">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {displayLosers.map((loser, index) => (
                    <LoserRow 
                      key={loser.id} 
                      loser={loser} 
                      rank={index + 1} 
                      onExplanationClick={handleExplanationClick}
                      onTopNewsClick={handleTopNewsClick}
                      onRegimeClick={handleRegimeClick}
                      regimeData={regimeData[loser.symbol]}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Generate Recommendations Button */}
        {displayLosers.length > 0 && displayLosers.some(l => !l.recommendation_id) && (
          <div className="mt-4 text-center">
            <button
              onClick={handleGenerateRecommendations}
              disabled={isGeneratingRecs}
              className={`px-6 py-3 rounded-lg font-medium transition ${
                isGeneratingRecs
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {isGeneratingRecs ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Generating AI Recommendations...
                </span>
              ) : (
                '🤖 Generate AI Recommendations for All'
              )}
            </button>
            <p className="text-xs text-gray-500 mt-2">Click to analyze all stocks with our AI recommendation engine</p>
          </div>
        )}

        {/* Top News Modal */}
        <TopNewsModal
          isOpen={isTopNewsModalOpen}
          onClose={() => {
            setIsTopNewsModalOpen(false)
            setTopNewsSymbol(null)
            setTopNewsArticles([])
          }}
          symbol={topNewsSymbol || ''}
          articles={topNewsArticles}
        />

        {/* Explanation Modal */}
        <ExplanationModal
          isOpen={isExplanationModalOpen}
          onClose={() => {
            setIsExplanationModalOpen(false)
            setSelectedLoser(null)
          }}
          loser={selectedLoser}
          regimeData={selectedLoser ? regimeData[selectedLoser.symbol] : undefined}
        />

        {/* Regime Display Modal */}
        {selectedRegimeSymbol && (
          <RegimeDisplay
            regime={regimeData[selectedRegimeSymbol] || null}
            symbol={selectedRegimeSymbol}
            onClose={handleRegimeClose}
            isLoading={!regimeData[selectedRegimeSymbol]}
          />
        )}

        {/* Footer Info */}
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>Data sourced from Yahoo Finance • Criteria: Market Cap &gt; $1B</p>
          <p>Service refreshes every 1 hour during market hours</p>
        </div>
      </div>
    </div>
  )
}
