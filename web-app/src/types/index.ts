export interface Recommendation {
  symbol: string
  action: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  suggestedOrder: {
    type: 'LIMIT' | 'MARKET'
    price: number
    quantity: number
  }
  explanation: {
    summary: string
    signals: {
      rsi?: number
      newsSentiment?: number
      socialMomentum?: number
    }
  }
}

export interface UserConfig {
  symbols: string[]
  riskLimits: {
    maxPositionPct: number
    maxTradesPerDay: number
  }
  signalWeights: {
    technical: number
    news: number
    social: number
  }
}

export interface SessionInfo {
  userId: string
  authenticated: boolean
  brokerageConnected: boolean
  brokerageTokenExpiresAt: string | null
}
