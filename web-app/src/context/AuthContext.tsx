import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { googleLogout } from '@react-oauth/google'
import { authenticateUser, getOnboardingData } from '../services/onboardingApi'

interface User {
  email: string
  name: string
  picture: string
  sub: string // Google user ID
  dbId?: string // Database user ID
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  isCheckingOnboarding: boolean
  isOnboardingComplete: boolean
  checkOnboardingCompletion: (userOverride?: User | null) => Promise<boolean>
  login: (credential: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isCheckingOnboarding, setIsCheckingOnboarding] = useState(false) // Only true while actively checking
  const [isOnboardingComplete, setIsOnboardingComplete] = useState(false)

  // Function to check if onboarding is 100% complete based on actual data
  const checkOnboardingCompletion = async (userOverride?: User | null): Promise<boolean> => {
    const currentUser = userOverride || user
    const userId = currentUser?.dbId || currentUser?.sub
    if (!userId) return false

    setIsCheckingOnboarding(true)
    try {
      const data = await getOnboardingData(userId)
      
      // Check profile completion (required fields: display_name, country, timezone)
      const profile = data.profile || {}
      const isProfileComplete = !!(
        profile.display_name?.trim() &&
        profile.country?.trim() &&
        profile.timezone?.trim()
      )
      
      // Check preferences completion
      const prefs = data.preferences || {}
      const isPreferencesComplete = !!(
        prefs.experience_level &&
        prefs.risk_tolerance &&
        prefs.trading_frequency &&
        prefs.investment_goals && prefs.investment_goals.length > 0 &&
        prefs.initial_investment_range
      )
      
      // Check watchlist completion (at least 1 stock)
      const watchlist = data.watchlist || []
      const isWatchlistComplete = watchlist.length > 0
      
      // Check brokerage connection (at least 1 active connection)
      const brokerageConnections = data.brokerageConnections || []
      const isBrokerageComplete = brokerageConnections.length > 0
      
      const complete = isProfileComplete && isPreferencesComplete && isBrokerageComplete && isWatchlistComplete
      setIsOnboardingComplete(complete)
      return complete
    } catch (error) {
      console.error('Error checking onboarding completion:', error)
      return false
    } finally {
      setIsCheckingOnboarding(false)
    }
  }

  useEffect(() => {
    // Check for existing session on mount
    const storedUser = localStorage.getItem('autotrader_user')
    
    if (storedUser) {
      try {
        const parsedUser = JSON.parse(storedUser)

        // If we somehow have a stored session without dbId, it cannot be used
        // for DB-backed pages. Clear it and require re-login.
        if (!parsedUser?.dbId) {
          localStorage.removeItem('autotrader_user')
        } else {
          setUser(parsedUser)
          // Set checking flag before async call
          setIsCheckingOnboarding(true)
          // Check onboarding completion for restored user
          checkOnboardingCompletion(parsedUser)
        }
      } catch {
        localStorage.removeItem('autotrader_user')
      }
    }
    // No else needed - isCheckingOnboarding is already false for unauthenticated users
    setIsLoading(false)
  }, [])

  const login = async (credential: string) => {
    try {
      // Decode the JWT credential from Google
      const payload = decodeJwt(credential)
      
      const userData: User = {
        email: payload.email,
        name: payload.name,
        picture: payload.picture,
        sub: payload.sub,
      }

      // Authenticate with backend and get/create user.
      // This app is DB-backed: without a DB user id (dbId) we cannot load
      // onboarding/watchlists/recommendations, so treat backend auth failure
      // as a login failure (no "local auth" fallback).
      const response = await authenticateUser({
        email: payload.email,
        name: payload.name,
        picture: payload.picture,
        googleId: payload.sub,
      })

      if (!response?.user?.id) {
        throw new Error('Backend authentication did not return a user id')
      }

      // Store database user ID
      userData.dbId = response.user.id

      setUser(userData)
      localStorage.setItem('autotrader_user', JSON.stringify(userData))
      
      // Set checking flag and check onboarding completion after login
      setIsCheckingOnboarding(true)
      await checkOnboardingCompletion(userData)
    } catch (error) {
      console.error('Login failed:', error)
      throw error
    }
  }

  const logout = () => {
    googleLogout()
    setUser(null)
    setIsOnboardingComplete(false)
    localStorage.removeItem('autotrader_user')
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        isCheckingOnboarding,
        isOnboardingComplete,
        checkOnboardingCompletion,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

// Helper function to decode JWT without verification (verification should happen on backend)
function decodeJwt(token: string): Record<string, string> {
  const base64Url = token.split('.')[1]
  const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
  const jsonPayload = decodeURIComponent(
    atob(base64)
      .split('')
      .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
      .join('')
  )
  return JSON.parse(jsonPayload)
}
