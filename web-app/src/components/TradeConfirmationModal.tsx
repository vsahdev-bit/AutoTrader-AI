import { useState, useEffect } from 'react'
import {
  createTradeAuthorization,
  executeTrade,
  cancelTrade,
  checkTradePinStatus,
  TradeDetails,
} from '../services/onboardingApi'

interface TradeConfirmationModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (execution: any) => void
  userId: string
  trade: TradeDetails | null
}

type Step = 'confirm' | 'authorize' | 'pin' | 'executing' | 'success' | 'error'

export default function TradeConfirmationModal({
  isOpen,
  onClose,
  onSuccess,
  userId,
  trade,
}: TradeConfirmationModalProps) {
  const [step, setStep] = useState<Step>('confirm')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tradeAuthId, setTradeAuthId] = useState<string | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<Date | null>(null)
  const [timeLeft, setTimeLeft] = useState<number>(0)
  const [hasPinEnabled, setHasPinEnabled] = useState(false)
  const [pin, setPin] = useState('')
  const [execution, setExecution] = useState<any>(null)

  // Check if user has PIN enabled
  useEffect(() => {
    if (userId && isOpen) {
      checkTradePinStatus(userId).then(res => {
        setHasPinEnabled(res.hasPinEnabled)
      })
    }
  }, [userId, isOpen])

  // Countdown timer
  useEffect(() => {
    if (!expiresAt) return

    const timer = setInterval(() => {
      const now = new Date()
      const diff = Math.max(0, Math.floor((expiresAt.getTime() - now.getTime()) / 1000))
      setTimeLeft(diff)

      if (diff === 0) {
        setError('Authorization expired. Please try again.')
        setStep('error')
      }
    }, 1000)

    return () => clearInterval(timer)
  }, [expiresAt])

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setStep('confirm')
      setError(null)
      setTradeAuthId(null)
      setToken(null)
      setExpiresAt(null)
      setPin('')
      setExecution(null)
    }
  }, [isOpen])

  const handleAuthorize = async () => {
    if (!trade) return

    setIsLoading(true)
    setError(null)

    try {
      const response = await createTradeAuthorization(userId, trade)

      if (response.success) {
        setTradeAuthId(response.tradeAuthId)
        setToken(response.token)
        setExpiresAt(new Date(response.expiresAt))
        setTimeLeft(response.ttlSeconds)
        setStep(hasPinEnabled ? 'pin' : 'authorize')
      } else {
        setError('Failed to create trade authorization')
        setStep('error')
      }
    } catch (err) {
      setError('Failed to authorize trade. Please try again.')
      setStep('error')
    } finally {
      setIsLoading(false)
    }
  }

  const handleExecute = async () => {
    if (!tradeAuthId || !token) return

    setIsLoading(true)
    setStep('executing')
    setError(null)

    try {
      const response = await executeTrade(userId, tradeAuthId, token, hasPinEnabled ? pin : undefined)

      if (response.success) {
        setExecution(response.execution)
        setStep('success')
        onSuccess(response.execution)
      } else {
        setError((response as any).error || 'Trade execution failed')
        setStep('error')
      }
    } catch (err) {
      setError('Failed to execute trade. Please try again.')
      setStep('error')
    } finally {
      setIsLoading(false)
    }
  }

  const handleCancel = async () => {
    if (tradeAuthId) {
      await cancelTrade(userId, tradeAuthId)
    }
    onClose()
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  if (!isOpen || !trade) return null

  const estimatedTotal = trade.quantity * (trade.limitPrice || 150) // Mock price for display

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={handleCancel} />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div className={`px-6 py-4 ${trade.action === 'BUY' ? 'bg-green-500' : 'bg-red-500'} text-white`}>
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">
              {trade.action === 'BUY' ? '📈 Buy' : '📉 Sell'} {trade.symbol}
            </h2>
            <button onClick={handleCancel} className="p-1 hover:bg-white/20 rounded-lg transition-colors">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          {expiresAt && step !== 'success' && step !== 'error' && (
            <div className="mt-2 flex items-center gap-2 text-sm text-white/80">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Authorization expires in: <span className="font-mono font-bold">{formatTime(timeLeft)}</span>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Step: Confirm */}
          {step === 'confirm' && (
            <div className="space-y-6">
              <div className="bg-gray-50 rounded-xl p-4 space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-500">Symbol</span>
                  <span className="font-semibold">{trade.symbol}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Action</span>
                  <span className={`font-semibold ${trade.action === 'BUY' ? 'text-green-600' : 'text-red-600'}`}>
                    {trade.action}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Quantity</span>
                  <span className="font-semibold">{trade.quantity} shares</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Order Type</span>
                  <span className="font-semibold capitalize">{trade.orderType || 'Market'}</span>
                </div>
                {trade.limitPrice && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Limit Price</span>
                    <span className="font-semibold">${trade.limitPrice.toFixed(2)}</span>
                  </div>
                )}
                <hr />
                <div className="flex justify-between text-lg">
                  <span className="text-gray-700">Estimated Total</span>
                  <span className="font-bold">${estimatedTotal.toFixed(2)}</span>
                </div>
              </div>

              <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 flex gap-3">
                <span className="text-xl">⚠️</span>
                <div className="text-sm text-yellow-800">
                  <p className="font-medium">Review your order carefully</p>
                  <p className="mt-1">Once confirmed, this trade will be executed immediately at market price.</p>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={handleCancel}
                  className="flex-1 px-4 py-3 border border-gray-300 rounded-xl font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAuthorize}
                  disabled={isLoading}
                  className={`flex-1 px-4 py-3 rounded-xl font-medium text-white transition-colors ${
                    trade.action === 'BUY'
                      ? 'bg-green-600 hover:bg-green-700'
                      : 'bg-red-600 hover:bg-red-700'
                  } disabled:opacity-50`}
                >
                  {isLoading ? (
                    <span className="flex items-center justify-center gap-2">
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Authorizing...
                    </span>
                  ) : (
                    'Continue'
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Step: PIN Entry */}
          {step === 'pin' && (
            <div className="space-y-6">
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-gray-900">Enter Your Trade PIN</h3>
                <p className="text-sm text-gray-500 mt-1">Enter your 4-6 digit PIN to confirm this trade</p>
              </div>

              <div className="flex justify-center gap-2">
                {[...Array(6)].map((_, i) => (
                  <div
                    key={i}
                    className={`w-10 h-12 rounded-lg border-2 flex items-center justify-center text-xl font-bold ${
                      pin.length > i ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                    }`}
                  >
                    {pin.length > i ? '•' : ''}
                  </div>
                ))}
              </div>

              <input
                type="tel"
                maxLength={6}
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
                className="sr-only"
                autoFocus
              />

              {/* Number pad */}
              <div className="grid grid-cols-3 gap-2">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, null, 0, 'del'].map((num, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      if (num === 'del') {
                        setPin(pin.slice(0, -1))
                      } else if (num !== null && pin.length < 6) {
                        setPin(pin + num)
                      }
                    }}
                    disabled={num === null}
                    className={`h-14 rounded-xl font-semibold text-xl transition-colors ${
                      num === null
                        ? 'invisible'
                        : num === 'del'
                        ? 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                    }`}
                  >
                    {num === 'del' ? '⌫' : num}
                  </button>
                ))}
              </div>

              <button
                onClick={handleExecute}
                disabled={pin.length < 4 || isLoading}
                className={`w-full px-4 py-3 rounded-xl font-medium text-white transition-colors ${
                  trade.action === 'BUY'
                    ? 'bg-green-600 hover:bg-green-700'
                    : 'bg-red-600 hover:bg-red-700'
                } disabled:opacity-50`}
              >
                Confirm Trade
              </button>
            </div>
          )}

          {/* Step: Authorize (no PIN) */}
          {step === 'authorize' && (
            <div className="space-y-6">
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-gray-900">Confirm Your Trade</h3>
                <p className="text-sm text-gray-500 mt-1">Click below to execute this trade</p>
              </div>

              <div className="bg-gray-50 rounded-xl p-4 text-center">
                <p className="text-2xl font-bold text-gray-900">
                  {trade.action} {trade.quantity} {trade.symbol}
                </p>
                <p className="text-gray-500 mt-1">≈ ${estimatedTotal.toFixed(2)}</p>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={handleCancel}
                  className="flex-1 px-4 py-3 border border-gray-300 rounded-xl font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleExecute}
                  disabled={isLoading}
                  className={`flex-1 px-4 py-3 rounded-xl font-medium text-white transition-colors ${
                    trade.action === 'BUY'
                      ? 'bg-green-600 hover:bg-green-700'
                      : 'bg-red-600 hover:bg-red-700'
                  } disabled:opacity-50`}
                >
                  Execute Trade
                </button>
              </div>
            </div>
          )}

          {/* Step: Executing */}
          {step === 'executing' && (
            <div className="py-8 text-center">
              <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900">Executing Trade...</h3>
              <p className="text-sm text-gray-500 mt-1">Please wait while we process your order</p>
            </div>
          )}

          {/* Step: Success */}
          {step === 'success' && execution && (
            <div className="space-y-6">
              <div className="text-center">
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-gray-900">Trade Executed!</h3>
                <p className="text-sm text-gray-500 mt-1">Your order has been successfully processed</p>
              </div>

              <div className="bg-green-50 rounded-xl p-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-600">Symbol</span>
                  <span className="font-semibold">{execution.symbol}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Action</span>
                  <span className="font-semibold">{execution.action}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Quantity</span>
                  <span className="font-semibold">{execution.quantity} shares</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Executed Price</span>
                  <span className="font-semibold">${execution.price.toFixed(2)}</span>
                </div>
                <hr />
                <div className="flex justify-between text-lg">
                  <span className="text-gray-700">Total</span>
                  <span className="font-bold text-green-600">${execution.total}</span>
                </div>
              </div>

              <div className="text-xs text-gray-500 text-center">
                Order ID: {execution.brokerOrderId}
              </div>

              <button
                onClick={onClose}
                className="w-full px-4 py-3 bg-gray-900 text-white rounded-xl font-medium hover:bg-gray-800 transition-colors"
              >
                Done
              </button>
            </div>
          )}

          {/* Step: Error */}
          {step === 'error' && (
            <div className="space-y-6">
              <div className="text-center">
                <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-gray-900">Trade Failed</h3>
                <p className="text-sm text-red-600 mt-1">{error}</p>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={onClose}
                  className="flex-1 px-4 py-3 border border-gray-300 rounded-xl font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Close
                </button>
                <button
                  onClick={() => {
                    setStep('confirm')
                    setError(null)
                  }}
                  className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors"
                >
                  Try Again
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
