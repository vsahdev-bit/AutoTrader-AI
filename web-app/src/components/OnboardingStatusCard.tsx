import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getOnboardingData, UserProfile, TradingPreferences, WatchlistStock, BrokerageConnection } from '../services/onboardingApi'

interface OnboardingStatusCardProps {
  userId: string
}

// Progress breakdown (5 sections, 20% each):
// Step 0 - Profile complete (display_name, country, timezone): 20%
// Step 1 - Experience level set: 20% (cumulative 40%)
// Step 2 - Trading Preferences complete (risk, frequency, goals, investment range): 20% (cumulative 60%)
// Step 3 - Brokerage connected: 20% (cumulative 80%)
// Step 4 - Watchlist has at least 1 stock: 20% (cumulative 100%)

export default function OnboardingStatusCard({ userId }: OnboardingStatusCardProps) {
  const navigate = useNavigate()
  const [isLoading, setIsLoading] = useState(true)
  const [percentage, setPercentage] = useState(0)

  useEffect(() => {
    async function loadProgress() {
      if (!userId) {
        setIsLoading(false)
        return
      }
      
      try {
        const data = await getOnboardingData(userId)
        
        // Check Step 0: Profile completion (required fields: display_name, country, timezone)
        const profile: UserProfile = data.profile || {}
        const isProfileComplete = !!(
          profile.display_name?.trim() &&
          profile.country?.trim() &&
          profile.timezone?.trim()
        )
        
        // Check Step 1: Experience level set
        const prefs: TradingPreferences = data.preferences || {}
        const isExperienceComplete = !!prefs.experience_level
        
        // Check Step 2: Trading Preferences complete (risk_tolerance, trading_frequency, investment_goals, initial_investment_range)
        const isPreferencesComplete = !!(
          prefs.risk_tolerance &&
          prefs.trading_frequency &&
          prefs.investment_goals && prefs.investment_goals.length > 0 &&
          prefs.initial_investment_range
        )
        
        // Check Step 3: Brokerage connection (at least 1 active connection)
        const brokerageConnections: BrokerageConnection[] = data.brokerageConnections || []
        const isBrokerageComplete = brokerageConnections.length > 0
        
        // Check Step 4: Watchlist completion (at least 1 stock)
        const watchlist: WatchlistStock[] = data.watchlist || []
        const isWatchlistComplete = watchlist.length > 0
        
        // Calculate percentage (5 sections, 20% each)
        let progress = 0
        if (isProfileComplete) progress += 20
        if (isExperienceComplete) progress += 20
        if (isPreferencesComplete) progress += 20
        if (isBrokerageComplete) progress += 20
        if (isWatchlistComplete) progress += 20
        setPercentage(progress)
        
      } catch (error) {
        console.error('Error loading onboarding progress:', error)
      } finally {
        setIsLoading(false)
      }
    }
    loadProgress()
  }, [userId])

  const getStatusConfig = () => {
    // Only show "Completed" when all 3 sections are filled (100%)
    if (percentage === 100) {
      return {
        label: 'Completed',
        color: 'text-green-600',
        bgColor: 'bg-green-50',
        borderColor: 'border-green-200',
        icon: (
          <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        ),
        progressColor: 'bg-green-500',
      }
    }
    if (percentage > 0) {
      return {
        label: 'In Progress',
        color: 'text-blue-600',
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-200',
        icon: (
          <svg className="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        ),
        progressColor: 'bg-blue-500',
      }
    }
    return {
      label: 'Not Started',
      color: 'text-gray-600',
      bgColor: 'bg-gray-50',
      borderColor: 'border-gray-200',
      icon: (
        <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
      progressColor: 'bg-gray-300',
    }
  }

  const config = getStatusConfig()
  const isComplete = percentage === 100

  if (isLoading) {
    return (
      <div className={`rounded-2xl border-2 border-gray-200 bg-gray-50 p-6 animate-pulse`}>
        <div className="h-8 w-8 bg-gray-200 rounded-full mb-4"></div>
        <div className="h-4 w-24 bg-gray-200 rounded mb-2"></div>
        <div className="h-3 w-32 bg-gray-200 rounded"></div>
      </div>
    )
  }

  return (
    <div className={`rounded-2xl border-2 ${config.borderColor} ${config.bgColor} p-6 transition-all hover:shadow-md`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          {config.icon}
        </div>
        <span className={`text-xs font-semibold px-2 py-1 rounded-full ${config.bgColor} ${config.color}`}>
          {config.label}
        </span>
      </div>

      {/* Title */}
      <h3 className="text-lg font-semibold text-gray-900 mb-1">Profile Setup</h3>
      <p className="text-sm text-gray-500 mb-4">
        {isComplete 
          ? 'Your profile is complete. You can edit your preferences anytime.'
          : percentage > 0
          ? 'Continue setting up your trading profile.'
          : 'Complete your profile to get personalized recommendations.'}
      </p>

      {/* Progress Bar */}
      <div className="mb-5">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-600">Progress</span>
          <span className={`font-medium ${config.color}`}>{percentage}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2.5">
          <div
            className={`${config.progressColor} h-2.5 rounded-full transition-all duration-500`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>

      {/* Action Button */}
      <button
        onClick={() => navigate('/onboarding')}
        className={`w-full py-3 px-4 rounded-xl font-medium transition-colors ${
          isComplete
            ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            : 'bg-blue-600 text-white hover:bg-blue-700'
        }`}
      >
        {isComplete 
          ? 'Edit Profile & Preferences'
          : percentage > 0
          ? 'Continue Setup'
          : 'Start Setup'}
      </button>
    </div>
  )
}
