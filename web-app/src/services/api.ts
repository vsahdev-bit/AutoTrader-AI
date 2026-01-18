import axios from 'axios'
import { Recommendation, UserConfig, SessionInfo } from '../types'

const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
})

export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  
  getSession: () =>
    api.get<SessionInfo>('/auth/session'),
  
  logout: () =>
    api.post('/auth/logout'),
}

export const recommendationApi = {
  getRecommendations: (limit: number = 5) =>
    api.get<{ recommendations: Recommendation[] }>('/recommendations', { params: { limit } }),
}

export const configApi = {
  getConfig: () =>
    api.get<UserConfig>('/config'),
  
  updateConfig: (config: UserConfig) =>
    api.put('/config', config),
}

export const tradeApi = {
  executeTrade: (trade: {
    symbol: string
    side: 'BUY' | 'SELL'
    orderType: 'MARKET' | 'LIMIT'
    quantity: number
    limitPrice?: number
  }, idempotencyKey: string) =>
    api.post('/trades/execute', trade, {
      headers: { 'Idempotency-Key': idempotencyKey }
    }),
}

export default api
