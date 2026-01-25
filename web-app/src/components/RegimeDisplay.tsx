/**
 * RegimeDisplay.tsx - Market Regime Display Component
 * 
 * Displays the current market regime classification for a stock,
 * including:
 * - Regime label and risk level
 * - 4 regime dimensions (volatility, trend, liquidity, information)
 * - Position sizing recommendations
 * - Stop-loss recommendations
 * - Warnings
 * 
 * The regime model helps traders understand current market conditions
 * and adjust their strategy accordingly.
 */

import { useState } from 'react'
import { RegimeResponse, RegimeInfo, PositionSizingInfo, StopLossInfo } from '../types'

/**
 * Props for the RegimeDisplay component
 */
interface RegimeDisplayProps {
  regime: RegimeResponse | null
  isLoading?: boolean
  compact?: boolean
}

/**
 * Get color classes for volatility level
 */
function getVolatilityColor(volatility: RegimeInfo['volatility']): string {
  switch (volatility) {
    case 'low': return 'bg-green-100 text-green-800'
    case 'normal': return 'bg-gray-100 text-gray-800'
    case 'high': return 'bg-orange-100 text-orange-800'
    case 'extreme': return 'bg-red-100 text-red-800'
    default: return 'bg-gray-100 text-gray-800'
  }
}

/**
 * Get color classes for trend
 */
function getTrendColor(trend: RegimeInfo['trend']): string {
  switch (trend) {
    case 'strong_uptrend': return 'bg-green-100 text-green-800'
    case 'uptrend': return 'bg-green-50 text-green-700'
    case 'mean_reverting': return 'bg-blue-100 text-blue-800'
    case 'choppy': return 'bg-yellow-100 text-yellow-800'
    case 'downtrend': return 'bg-red-50 text-red-700'
    case 'strong_downtrend': return 'bg-red-100 text-red-800'
    default: return 'bg-gray-100 text-gray-800'
  }
}

/**
 * Get icon for trend
 */
function getTrendIcon(trend: RegimeInfo['trend']): string {
  switch (trend) {
    case 'strong_uptrend': return '📈'
    case 'uptrend': return '↗️'
    case 'mean_reverting': return '↔️'
    case 'choppy': return '〰️'
    case 'downtrend': return '↘️'
    case 'strong_downtrend': return '📉'
    default: return '➡️'
  }
}

/**
 * Format trend label for display
 */
function formatTrendLabel(trend: RegimeInfo['trend']): string {
  return trend.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

/**
 * Get color classes for liquidity
 */
function getLiquidityColor(liquidity: RegimeInfo['liquidity']): string {
  switch (liquidity) {
    case 'high': return 'bg-green-100 text-green-800'
    case 'normal': return 'bg-gray-100 text-gray-800'
    case 'thin': return 'bg-orange-100 text-orange-800'
    case 'illiquid': return 'bg-red-100 text-red-800'
    default: return 'bg-gray-100 text-gray-800'
  }
}

/**
 * Get color classes for information regime
 */
function getInfoColor(info: RegimeInfo['information']): string {
  switch (info) {
    case 'quiet': return 'bg-gray-100 text-gray-700'
    case 'normal': return 'bg-gray-100 text-gray-800'
    case 'news_driven': return 'bg-blue-100 text-blue-800'
    case 'social_driven': return 'bg-purple-100 text-purple-800'
    case 'earnings': return 'bg-amber-100 text-amber-800'
    default: return 'bg-gray-100 text-gray-800'
  }
}

/**
 * Format information regime label
 */
function formatInfoLabel(info: RegimeInfo['information']): string {
  switch (info) {
    case 'news_driven': return 'News-Driven'
    case 'social_driven': return 'Social-Driven'
    default: return info.charAt(0).toUpperCase() + info.slice(1)
  }
}

/**
 * Compact regime badge for table views
 */
export function RegimeBadge({ regime }: { regime: RegimeResponse | null }) {
  if (!regime) return null
  
  const isHighRisk = regime.regime.risk_level === 'high'
  
  return (
    <div className="flex items-center gap-2">
      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
        isHighRisk ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
      }`}>
        {isHighRisk ? '⚠️' : '✓'} {regime.regime.label || 'Normal'}
      </span>
      {regime.position_sizing && (
        <span className="text-xs text-gray-500">
          {(regime.position_sizing.size_multiplier * 100).toFixed(0)}% size
        </span>
      )}
    </div>
  )
}

/**
 * Position Sizing Card
 */
function PositionSizingCard({ sizing }: { sizing: PositionSizingInfo }) {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
      <h4 className="text-sm font-semibold text-blue-900 mb-3 flex items-center gap-2">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
        Position Sizing
      </h4>
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm text-blue-700">Size Multiplier:</span>
          <span className={`font-bold text-lg ${
            sizing.size_multiplier < 0.5 ? 'text-red-600' :
            sizing.size_multiplier < 0.8 ? 'text-orange-600' :
            sizing.size_multiplier > 1 ? 'text-green-600' : 'text-gray-900'
          }`}>
            {(sizing.size_multiplier * 100).toFixed(0)}%
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-blue-700">Max Position:</span>
          <span className="font-semibold text-gray-900">{sizing.max_position_percent}%</span>
        </div>
        {sizing.scale_in_entries > 1 && (
          <div className="flex justify-between items-center">
            <span className="text-sm text-blue-700">Scale-In:</span>
            <span className="font-semibold text-gray-900">{sizing.scale_in_entries} entries</span>
          </div>
        )}
        {sizing.reasoning && (
          <p className="text-xs text-blue-600 mt-2 pt-2 border-t border-blue-200">
            💡 {sizing.reasoning}
          </p>
        )}
      </div>
    </div>
  )
}

/**
 * Stop Loss Card
 */
function StopLossCard({ stopLoss }: { stopLoss: StopLossInfo }) {
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
      <h4 className="text-sm font-semibold text-amber-900 mb-3 flex items-center gap-2">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        Stop-Loss Strategy
      </h4>
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm text-amber-700">ATR Multiplier:</span>
          <span className="font-bold text-lg text-gray-900">{stopLoss.atr_multiplier}x</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-amber-700">Stop Distance:</span>
          <span className="font-semibold text-gray-900">{stopLoss.percent_from_entry}%</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-amber-700">Risk:Reward:</span>
          <span className="font-semibold text-gray-900">1:{stopLoss.risk_reward_ratio}</span>
        </div>
        {stopLoss.use_trailing_stop && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-green-600">✓</span>
            <span className="text-amber-700">Use trailing stop</span>
          </div>
        )}
        {stopLoss.reasoning && (
          <p className="text-xs text-amber-600 mt-2 pt-2 border-t border-amber-200">
            💡 {stopLoss.reasoning}
          </p>
        )}
      </div>
    </div>
  )
}

/**
 * Main RegimeDisplay Component
 */
export default function RegimeDisplay({ regime, isLoading, compact = false }: RegimeDisplayProps) {
  const [expanded, setExpanded] = useState(!compact)
  
  if (isLoading) {
    return (
      <div className="animate-pulse bg-gray-100 rounded-lg p-4">
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-2"></div>
        <div className="h-3 bg-gray-200 rounded w-2/3"></div>
      </div>
    )
  }
  
  if (!regime) {
    return null
  }
  
  const { regime: regimeInfo, position_sizing, stop_loss, signal_weights } = regime
  const isHighRisk = regimeInfo.risk_level === 'high'
  
  // Compact view for inline display
  if (compact && !expanded) {
    return (
      <div 
        className={`rounded-lg p-3 cursor-pointer transition-all hover:shadow-md ${
          isHighRisk ? 'bg-red-50 border border-red-200' : 'bg-gray-50 border border-gray-200'
        }`}
        onClick={() => setExpanded(true)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`text-lg ${isHighRisk ? 'animate-pulse' : ''}`}>
              {isHighRisk ? '⚠️' : '📊'}
            </span>
            <div>
              <span className="font-medium text-gray-900">{regimeInfo.label}</span>
              <span className="text-xs text-gray-500 ml-2">
                Risk: {(regimeInfo.risk_score * 100).toFixed(0)}%
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {position_sizing && (
              <span className="text-sm font-medium text-blue-600">
                {(position_sizing.size_multiplier * 100).toFixed(0)}% size
              </span>
            )}
            <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
        {regimeInfo.warnings.length > 0 && (
          <p className="text-xs text-red-600 mt-1">⚠️ {regimeInfo.warnings[0]}</p>
        )}
      </div>
    )
  }
  
  // Full expanded view
  return (
    <div className={`rounded-xl border ${
      isHighRisk ? 'bg-red-50/50 border-red-200' : 'bg-white border-gray-200'
    }`}>
      {/* Header */}
      <div 
        className={`p-4 border-b cursor-pointer ${
          isHighRisk ? 'border-red-200' : 'border-gray-200'
        }`}
        onClick={() => compact && setExpanded(false)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center text-xl ${
              isHighRisk ? 'bg-red-100' : 'bg-green-100'
            }`}>
              {isHighRisk ? '⚠️' : '✓'}
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">{regimeInfo.label}</h3>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  isHighRisk ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                }`}>
                  {isHighRisk ? 'High Risk' : 'Normal Risk'}
                </span>
                <span className="text-xs text-gray-500">
                  Score: {(regimeInfo.risk_score * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
          {compact && (
            <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          )}
        </div>
        
        {/* Warnings */}
        {regimeInfo.warnings.length > 0 && (
          <div className="mt-3 space-y-1">
            {regimeInfo.warnings.map((warning, idx) => (
              <p key={idx} className="text-sm text-red-600 flex items-center gap-2">
                <span>⚠️</span> {warning}
              </p>
            ))}
          </div>
        )}
      </div>
      
      {/* Regime Dimensions */}
      <div className="p-4 border-b border-gray-200">
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Market Conditions
        </h4>
        <div className="grid grid-cols-2 gap-3">
          {/* Volatility */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Volatility</span>
            <span className={`px-2 py-1 rounded text-xs font-medium ${getVolatilityColor(regimeInfo.volatility)}`}>
              {regimeInfo.volatility.toUpperCase()}
            </span>
          </div>
          
          {/* Trend */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Trend</span>
            <span className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 ${getTrendColor(regimeInfo.trend)}`}>
              {getTrendIcon(regimeInfo.trend)} {formatTrendLabel(regimeInfo.trend)}
            </span>
          </div>
          
          {/* Liquidity */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Liquidity</span>
            <span className={`px-2 py-1 rounded text-xs font-medium ${getLiquidityColor(regimeInfo.liquidity)}`}>
              {regimeInfo.liquidity.toUpperCase()}
            </span>
          </div>
          
          {/* Information */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">News Flow</span>
            <span className={`px-2 py-1 rounded text-xs font-medium ${getInfoColor(regimeInfo.information)}`}>
              {formatInfoLabel(regimeInfo.information)}
            </span>
          </div>
        </div>
      </div>
      
      {/* Signal Weights */}
      <div className="p-4 border-b border-gray-200">
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Signal Weights (Regime-Adjusted)
        </h4>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 w-28">News Sentiment</span>
            <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-blue-500 rounded-full" 
                style={{ width: `${signal_weights.news_sentiment * 100}%` }}
              />
            </div>
            <span className="text-xs font-medium text-gray-700 w-12 text-right">
              {(signal_weights.news_sentiment * 100).toFixed(0)}%
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 w-28">News Momentum</span>
            <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-indigo-500 rounded-full" 
                style={{ width: `${signal_weights.news_momentum * 100}%` }}
              />
            </div>
            <span className="text-xs font-medium text-gray-700 w-12 text-right">
              {(signal_weights.news_momentum * 100).toFixed(0)}%
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 w-28">Tech Trend</span>
            <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-cyan-500 rounded-full" 
                style={{ width: `${signal_weights.technical_trend * 100}%` }}
              />
            </div>
            <span className="text-xs font-medium text-gray-700 w-12 text-right">
              {(signal_weights.technical_trend * 100).toFixed(0)}%
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 w-28">Tech Momentum</span>
            <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-teal-500 rounded-full" 
                style={{ width: `${signal_weights.technical_momentum * 100}%` }}
              />
            </div>
            <span className="text-xs font-medium text-gray-700 w-12 text-right">
              {(signal_weights.technical_momentum * 100).toFixed(0)}%
            </span>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-gray-500">Confidence Multiplier:</span>
          <span className={`text-sm font-semibold ${
            signal_weights.confidence_multiplier < 0.5 ? 'text-red-600' :
            signal_weights.confidence_multiplier < 0.8 ? 'text-orange-600' :
            'text-green-600'
          }`}>
            {(signal_weights.confidence_multiplier * 100).toFixed(0)}%
          </span>
        </div>
      </div>
      
      {/* Position Sizing & Stop Loss */}
      {(position_sizing || stop_loss) && (
        <div className="p-4">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Risk Management
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {position_sizing && <PositionSizingCard sizing={position_sizing} />}
            {stop_loss && <StopLossCard stopLoss={stop_loss} />}
          </div>
        </div>
      )}
    </div>
  )
}
