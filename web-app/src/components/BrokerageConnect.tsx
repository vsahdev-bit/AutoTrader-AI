import { useState, useEffect } from 'react'
import {
  createPlaidLinkToken,
  exchangePlaidToken,
  getBrokerageConnections,
  disconnectBrokerage,
  BrokerageConnection,
} from '../services/onboardingApi'

interface BrokerageConnectProps {
  userId: string
  onConnectionChange?: (hasConnection: boolean) => void
}

// Brokerage logos/icons
const BROKERAGES = [
  { id: 'robinhood', name: 'Robinhood', color: 'bg-green-500', icon: '🪶' },
  { id: 'fidelity', name: 'Fidelity', color: 'bg-green-600', icon: '💼' },
  { id: 'schwab', name: 'Charles Schwab', color: 'bg-blue-600', icon: '📊' },
  { id: 'etrade', name: 'E*TRADE', color: 'bg-purple-600', icon: '📈' },
  { id: 'td_ameritrade', name: 'TD Ameritrade', color: 'bg-green-700', icon: '🏦' },
  { id: 'vanguard', name: 'Vanguard', color: 'bg-red-700', icon: '⚓' },
]

export default function BrokerageConnect({ userId, onConnectionChange }: BrokerageConnectProps) {
  const [connections, setConnections] = useState<BrokerageConnection[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isConnecting, setIsConnecting] = useState(false)
  const [selectedBrokerage, setSelectedBrokerage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load existing connections
  useEffect(() => {
    async function loadConnections() {
      if (!userId) {
        setIsLoading(false)
        return
      }
      
      try {
        const data = await getBrokerageConnections(userId)
        const activeConnections = data.connections.filter(c => c.status === 'active')
        setConnections(activeConnections)
        onConnectionChange?.(activeConnections.length > 0)
      } catch (error) {
        console.error('Error loading connections:', error)
      } finally {
        setIsLoading(false)
      }
    }
    
    loadConnections()
  }, [userId, onConnectionChange])

  const handleConnect = async (brokerageId: string, brokerageName: string) => {
    setIsConnecting(true)
    setSelectedBrokerage(brokerageId)
    setError(null)
    
    try {
      // First, try to create a Plaid Link token
      const linkResponse = await createPlaidLinkToken(userId)
      
      if (linkResponse.sandbox || !linkResponse.linkToken) {
        // Sandbox mode - simulate the connection flow
        // In production, this would open Plaid Link
        
        // Simulate a brief loading state
        await new Promise(resolve => setTimeout(resolve, 1500))
        
        // Exchange token (sandbox mode will create mock data)
        const exchangeResponse = await exchangePlaidToken({
          userId,
          publicToken: 'sandbox-public-token',
          institutionId: `ins_${brokerageId}`,
          institutionName: brokerageName,
        })
        
        if (exchangeResponse.success && exchangeResponse.connection) {
          setConnections(prev => [...prev, exchangeResponse.connection!])
          onConnectionChange?.(true)
        }
      } else {
        // Production mode - would integrate with Plaid Link
        // This requires adding react-plaid-link package
        // For now, show a message
        setError('Plaid Link integration requires additional setup. Using sandbox mode.')
        
        // Fallback to sandbox
        const exchangeResponse = await exchangePlaidToken({
          userId,
          publicToken: 'sandbox-public-token',
          institutionId: `ins_${brokerageId}`,
          institutionName: brokerageName,
        })
        
        if (exchangeResponse.success && exchangeResponse.connection) {
          setConnections(prev => [...prev, exchangeResponse.connection!])
          onConnectionChange?.(true)
        }
      }
    } catch (err) {
      console.error('Connection error:', err)
      setError('Failed to connect. Please try again.')
    } finally {
      setIsConnecting(false)
      setSelectedBrokerage(null)
    }
  }

  const handleDisconnect = async (connectionId: string) => {
    try {
      await disconnectBrokerage(userId, connectionId)
      const updatedConnections = connections.filter(c => c.id !== connectionId)
      setConnections(updatedConnections)
      onConnectionChange?.(updatedConnections.length > 0)
    } catch (error) {
      console.error('Error disconnecting:', error)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Connected Accounts */}
      {connections.length > 0 && (
        <div className="mb-8">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Connected Accounts</h3>
          <div className="space-y-3">
            {connections.map((connection) => (
              <div
                key={connection.id}
                className="flex items-center justify-between p-4 bg-green-50 border border-green-200 rounded-xl"
              >
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-green-500 rounded-xl flex items-center justify-center text-white text-xl">
                    ✓
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">{connection.institution_name}</p>
                    <p className="text-sm text-green-600">Connected</p>
                  </div>
                </div>
                <button
                  onClick={() => handleDisconnect(connection.id)}
                  className="px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                >
                  Disconnect
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Available Brokerages */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">
          {connections.length > 0 ? 'Connect Another Account' : 'Select Your Brokerage'}
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {BROKERAGES.map((brokerage) => {
            const isConnected = connections.some(
              c => c.institution_name.toLowerCase().includes(brokerage.id) ||
                   c.institution_id?.includes(brokerage.id)
            )
            const isCurrentlyConnecting = isConnecting && selectedBrokerage === brokerage.id
            
            return (
              <button
                key={brokerage.id}
                onClick={() => !isConnected && handleConnect(brokerage.id, brokerage.name)}
                disabled={isConnecting || isConnected}
                className={`p-4 rounded-xl border-2 text-left transition-all ${
                  isConnected
                    ? 'border-green-300 bg-green-50 cursor-default'
                    : isCurrentlyConnecting
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50'
                } disabled:opacity-60`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 ${brokerage.color} rounded-lg flex items-center justify-center text-white text-lg`}>
                    {brokerage.icon}
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{brokerage.name}</p>
                    {isConnected && (
                      <p className="text-xs text-green-600">Connected</p>
                    )}
                    {isCurrentlyConnecting && (
                      <p className="text-xs text-blue-600 flex items-center gap-1">
                        <span className="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></span>
                        Connecting...
                      </p>
                    )}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Info Box */}
      <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
        <div className="flex gap-3">
          <div className="text-2xl">🔒</div>
          <div>
            <p className="font-medium text-blue-900">Secure Connection</p>
            <p className="text-sm text-blue-700 mt-1">
              We use Plaid, a trusted financial data platform, to securely connect to your brokerage. 
              We never store your login credentials.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
