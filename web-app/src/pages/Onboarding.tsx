import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  getOnboardingData,
  updateOnboardingStatus,
  updateProfile,
  updatePreferences,
  UserProfile,
  TradingPreferences,
  WatchlistStock,
  BrokerageConnection,
} from '../services/onboardingApi'
import StockSearch from '../components/StockSearch'
import BrokerageConnect from '../components/BrokerageConnect'
import Header from '../components/Header'

const STEPS = [
  { id: 0, title: 'Profile', description: 'Tell us about yourself' },
  { id: 1, title: 'Experience', description: 'Your trading background' },
  { id: 2, title: 'Preferences', description: 'Investment preferences' },
  { id: 3, title: 'Brokerage', description: 'Connect your brokerage account' },
  { id: 4, title: 'Watchlist', description: 'Add stocks to watch' },
]

interface ValidationErrors {
  [key: string]: string
}

export default function Onboarding() {
  const navigate = useNavigate()
  const { user, checkOnboardingCompletion } = useAuth()
  const [currentStep, setCurrentStep] = useState(0)
  const [completedSteps, setCompletedSteps] = useState<number[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [errors, setErrors] = useState<ValidationErrors>({})

  // Form data
  const [profile, setProfile] = useState<UserProfile>({
    display_name: '',
    phone: '',
    country: '',
    timezone: '',
  })
  const [preferences, setPreferences] = useState<TradingPreferences>({
    experience_level: undefined,
    investment_goals: [],
    risk_tolerance: undefined,
    trading_frequency: undefined,
    initial_investment_range: undefined,
  })
  const [watchlist, setWatchlist] = useState<WatchlistStock[]>([])
  // Note: brokerageConnections is loaded for calculating initial completedSteps,
  // but the BrokerageConnect component manages its own connection state
  const [, setBrokerageConnections] = useState<BrokerageConnection[]>([])

  // Get the user ID (prefer database ID, fallback to Google sub)
  const userId = user?.dbId || user?.sub

  // Load existing onboarding data
  useEffect(() => {
    async function loadData() {
      if (!userId) {
        // No user ID yet, stop loading but don't fetch
        setIsLoading(false)
        return
      }
      
      try {
        const data = await getOnboardingData(userId)
        
        // Load profile data
        const loadedProfile = data.profile ? {
          display_name: data.profile.display_name || user?.name || '',
          phone: data.profile.phone || '',
          country: data.profile.country || '',
          timezone: data.profile.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone,
        } : {
          display_name: user?.name || '',
          phone: '',
          country: '',
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        }
        setProfile(loadedProfile)
        
        // Load preferences data
        const loadedPreferences = data.preferences || preferences
        if (data.preferences) {
          setPreferences(data.preferences)
        }
        
        // Load watchlist data
        const loadedWatchlist = data.watchlist || []
        setWatchlist(loadedWatchlist)
        
        // Load brokerage connections
        const loadedBrokerageConnections = data.brokerageConnections || []
        setBrokerageConnections(loadedBrokerageConnections)
        
        // Calculate completedSteps dynamically based on actual data
        const calculatedCompletedSteps: number[] = []
        
        // Step 0: Profile - complete if display_name, country, and timezone are filled
        if (loadedProfile.display_name?.trim() && loadedProfile.country?.trim() && loadedProfile.timezone?.trim()) {
          calculatedCompletedSteps.push(0)
        }
        
        // Step 1: Experience - complete if experience_level is set
        if (loadedPreferences.experience_level) {
          calculatedCompletedSteps.push(1)
        }
        
        // Step 2: Preferences - complete if risk_tolerance, trading_frequency, investment_goals, and initial_investment_range are set
        if (loadedPreferences.risk_tolerance && 
            loadedPreferences.trading_frequency && 
            loadedPreferences.investment_goals && loadedPreferences.investment_goals.length > 0 &&
            loadedPreferences.initial_investment_range) {
          calculatedCompletedSteps.push(2)
        }
        
        // Step 3: Brokerage - complete if at least 1 brokerage connection exists
        if (loadedBrokerageConnections.length > 0) {
          calculatedCompletedSteps.push(3)
        }
        
        // Step 4: Watchlist - complete if at least 1 stock in watchlist
        if (loadedWatchlist.length > 0) {
          calculatedCompletedSteps.push(4)
        }
        
        setCompletedSteps(calculatedCompletedSteps)
        
        // Set current step from database or default to 0
        if (data.onboarding) {
          const step = data.onboarding.current_step || 0
          setCurrentStep(Math.min(step, STEPS.length - 1))
        }
      } catch (error) {
        console.error('Error loading onboarding data:', error)
      } finally {
        setIsLoading(false)
      }
    }
    
    loadData()
  }, [userId, user?.name])

  // Validation functions
  const validateStep0 = (): boolean => {
    const newErrors: ValidationErrors = {}
    
    if (!profile.display_name?.trim()) {
      newErrors.display_name = 'Display name is required'
    } else if (profile.display_name.trim().length < 2) {
      newErrors.display_name = 'Display name must be at least 2 characters'
    }
    
    if (profile.phone && !/^[\d\s\-\+\(\)]+$/.test(profile.phone)) {
      newErrors.phone = 'Please enter a valid phone number'
    }
    
    if (!profile.country) {
      newErrors.country = 'Please select your country'
    }
    
    if (!profile.timezone) {
      newErrors.timezone = 'Please select your timezone'
    }
    
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const validateStep1 = (): boolean => {
    const newErrors: ValidationErrors = {}
    
    if (!preferences.experience_level) {
      newErrors.experience_level = 'Please select your experience level'
    }
    
    if (!preferences.trading_frequency) {
      newErrors.trading_frequency = 'Please select your trading frequency'
    }
    
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const validateStep2 = (): boolean => {
    const newErrors: ValidationErrors = {}
    
    if (!preferences.risk_tolerance) {
      newErrors.risk_tolerance = 'Please select your risk tolerance'
    }
    
    if (!preferences.investment_goals || preferences.investment_goals.length === 0) {
      newErrors.investment_goals = 'Please select at least one investment goal'
    }
    
    if (!preferences.initial_investment_range) {
      newErrors.initial_investment_range = 'Please select your investment range'
    }
    
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const validateCurrentStep = (): boolean => {
    switch (currentStep) {
      case 0: return validateStep0()
      case 1: return validateStep1()
      case 2: return validateStep2()
      case 3: return true // Brokerage is optional
      case 4: return true // Watchlist is optional
      default: return true
    }
  }

  const handleSaveStep = async () => {
    if (!userId) return
    
    // Validate current step
    if (!validateCurrentStep()) {
      return
    }
    
    setIsSaving(true)
    try {
      // Save current step data
      if (currentStep === 0) {
        await updateProfile(userId, profile)
      } else if (currentStep === 1 || currentStep === 2) {
        await updatePreferences(userId, preferences)
      }
      
      // Mark step as completed
      const newCompletedSteps = [...new Set([...completedSteps, currentStep])]
      setCompletedSteps(newCompletedSteps)
      
      // Update onboarding status
      await updateOnboardingStatus(userId, {
        status: 'in_progress',
        currentStep: currentStep + 1,
        completedSteps: newCompletedSteps,
      })
      
      // Clear errors and move to next step
      setErrors({})
      if (currentStep < STEPS.length - 1) {
        setCurrentStep(currentStep + 1)
      }
    } catch (error) {
      console.error('Error saving step:', error)
    } finally {
      setIsSaving(false)
    }
  }

  const handleComplete = async () => {
    if (!userId) return
    
    setIsSaving(true)
    try {
      // Re-check completion status and navigate to dashboard
      await checkOnboardingCompletion()
      navigate('/dashboard')
    } catch (error) {
      console.error('Error completing onboarding:', error)
    } finally {
      setIsSaving(false)
    }
  }

  const handleWatchlistUpdate = (stocks: WatchlistStock[]) => {
    setWatchlist(stocks)
  }

  const handleBack = () => {
    setErrors({})
    setCurrentStep(Math.max(0, currentStep - 1))
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      {/* Onboarding Progress Indicator */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900">Complete Your Profile</h1>
          <div className="text-sm text-gray-500">
            Step {currentStep + 1} of {STEPS.length}
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            {STEPS.map((step, index) => (
              <div key={step.id} className="flex items-center">
                <div className="flex flex-col items-center">
                  <button
                    onClick={() => setCurrentStep(step.id)}
                    className={`w-10 h-10 rounded-full flex items-center justify-center font-medium text-sm transition-all cursor-pointer hover:scale-110 ${
                      completedSteps.includes(step.id)
                        ? 'bg-green-500 text-white hover:bg-green-600'
                        : currentStep === step.id
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-500 hover:bg-gray-300'
                    }`}
                    title={`Go to ${step.title}`}
                  >
                    {completedSteps.includes(step.id) ? (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      step.id + 1
                    )}
                  </button>
                  <button
                    onClick={() => setCurrentStep(step.id)}
                    className={`mt-2 text-xs font-medium cursor-pointer hover:underline ${currentStep === step.id ? 'text-blue-600' : 'text-gray-500 hover:text-gray-700'}`}
                  >
                    {step.title}
                  </button>
                </div>
                {index < STEPS.length - 1 && (
                  <div className={`w-full h-1 mx-2 ${completedSteps.includes(step.id) ? 'bg-green-500' : 'bg-gray-200'}`} style={{ minWidth: '60px' }} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Step Content */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">{STEPS[currentStep].title}</h2>
          <p className="text-gray-500 mb-8">{STEPS[currentStep].description}</p>

          {/* Step 0: Profile */}
          {currentStep === 0 && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Display Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={profile.display_name || ''}
                  onChange={(e) => {
                    setProfile({ ...profile, display_name: e.target.value })
                    if (errors.display_name) setErrors({ ...errors, display_name: '' })
                  }}
                  className={`w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                    errors.display_name ? 'border-red-500' : 'border-gray-300'
                  }`}
                  placeholder="John Doe"
                />
                {errors.display_name && (
                  <p className="mt-1 text-sm text-red-500">{errors.display_name}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Phone Number</label>
                <input
                  type="tel"
                  value={profile.phone || ''}
                  onChange={(e) => {
                    setProfile({ ...profile, phone: e.target.value })
                    if (errors.phone) setErrors({ ...errors, phone: '' })
                  }}
                  className={`w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                    errors.phone ? 'border-red-500' : 'border-gray-300'
                  }`}
                  placeholder="+1 (555) 123-4567"
                />
                {errors.phone && (
                  <p className="mt-1 text-sm text-red-500">{errors.phone}</p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Country <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={profile.country || ''}
                    onChange={(e) => {
                      setProfile({ ...profile, country: e.target.value })
                      if (errors.country) setErrors({ ...errors, country: '' })
                    }}
                    className={`w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                      errors.country ? 'border-red-500' : 'border-gray-300'
                    }`}
                  >
                    <option value="">Select country</option>
                    <option value="US">United States</option>
                    <option value="UK">United Kingdom</option>
                    <option value="CA">Canada</option>
                    <option value="AU">Australia</option>
                    <option value="DE">Germany</option>
                    <option value="FR">France</option>
                    <option value="IN">India</option>
                    <option value="JP">Japan</option>
                    <option value="SG">Singapore</option>
                  </select>
                  {errors.country && (
                    <p className="mt-1 text-sm text-red-500">{errors.country}</p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Timezone <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={profile.timezone || ''}
                    onChange={(e) => {
                      setProfile({ ...profile, timezone: e.target.value })
                      if (errors.timezone) setErrors({ ...errors, timezone: '' })
                    }}
                    className={`w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                      errors.timezone ? 'border-red-500' : 'border-gray-300'
                    }`}
                  >
                    <option value="">Select timezone</option>
                    <option value="America/New_York">Eastern Time (ET)</option>
                    <option value="America/Chicago">Central Time (CT)</option>
                    <option value="America/Denver">Mountain Time (MT)</option>
                    <option value="America/Los_Angeles">Pacific Time (PT)</option>
                    <option value="Europe/London">London (GMT)</option>
                    <option value="Europe/Paris">Paris (CET)</option>
                    <option value="Asia/Tokyo">Tokyo (JST)</option>
                    <option value="Asia/Singapore">Singapore (SGT)</option>
                  </select>
                  {errors.timezone && (
                    <p className="mt-1 text-sm text-red-500">{errors.timezone}</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Step 1: Experience */}
          {currentStep === 1 && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Trading Experience Level <span className="text-red-500">*</span>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { value: 'beginner', label: 'Beginner', desc: 'New to trading' },
                    { value: 'intermediate', label: 'Intermediate', desc: '1-3 years experience' },
                    { value: 'advanced', label: 'Advanced', desc: '3-5 years experience' },
                    { value: 'expert', label: 'Expert', desc: '5+ years experience' },
                  ].map((option) => (
                    <button
                      key={option.value}
                      onClick={() => {
                        setPreferences({ ...preferences, experience_level: option.value as any })
                        if (errors.experience_level) setErrors({ ...errors, experience_level: '' })
                      }}
                      className={`p-4 rounded-lg border-2 text-left transition-all ${
                        preferences.experience_level === option.value
                          ? 'border-blue-500 bg-blue-50'
                          : errors.experience_level
                          ? 'border-red-300 hover:border-red-400'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="font-medium text-gray-900">{option.label}</div>
                      <div className="text-sm text-gray-500">{option.desc}</div>
                    </button>
                  ))}
                </div>
                {errors.experience_level && (
                  <p className="mt-2 text-sm text-red-500">{errors.experience_level}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  How often do you trade? <span className="text-red-500">*</span>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { value: 'daily', label: 'Daily', desc: 'Multiple times per day' },
                    { value: 'weekly', label: 'Weekly', desc: 'Few times per week' },
                    { value: 'monthly', label: 'Monthly', desc: 'Few times per month' },
                    { value: 'occasional', label: 'Occasional', desc: 'When opportunities arise' },
                  ].map((option) => (
                    <button
                      key={option.value}
                      onClick={() => {
                        setPreferences({ ...preferences, trading_frequency: option.value as any })
                        if (errors.trading_frequency) setErrors({ ...errors, trading_frequency: '' })
                      }}
                      className={`p-4 rounded-lg border-2 text-left transition-all ${
                        preferences.trading_frequency === option.value
                          ? 'border-blue-500 bg-blue-50'
                          : errors.trading_frequency
                          ? 'border-red-300 hover:border-red-400'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="font-medium text-gray-900">{option.label}</div>
                      <div className="text-sm text-gray-500">{option.desc}</div>
                    </button>
                  ))}
                </div>
                {errors.trading_frequency && (
                  <p className="mt-2 text-sm text-red-500">{errors.trading_frequency}</p>
                )}
              </div>
            </div>
          )}

          {/* Step 2: Preferences */}
          {currentStep === 2 && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Risk Tolerance <span className="text-red-500">*</span>
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { value: 'conservative', label: 'Conservative', desc: 'Lower risk, steady growth', icon: '🛡️' },
                    { value: 'moderate', label: 'Moderate', desc: 'Balanced approach', icon: '⚖️' },
                    { value: 'aggressive', label: 'Aggressive', desc: 'Higher risk, higher potential', icon: '🚀' },
                  ].map((option) => (
                    <button
                      key={option.value}
                      onClick={() => {
                        setPreferences({ ...preferences, risk_tolerance: option.value as any })
                        if (errors.risk_tolerance) setErrors({ ...errors, risk_tolerance: '' })
                      }}
                      className={`p-4 rounded-lg border-2 text-center transition-all ${
                        preferences.risk_tolerance === option.value
                          ? 'border-blue-500 bg-blue-50'
                          : errors.risk_tolerance
                          ? 'border-red-300 hover:border-red-400'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="text-2xl mb-2">{option.icon}</div>
                      <div className="font-medium text-gray-900">{option.label}</div>
                      <div className="text-xs text-gray-500">{option.desc}</div>
                    </button>
                  ))}
                </div>
                {errors.risk_tolerance && (
                  <p className="mt-2 text-sm text-red-500">{errors.risk_tolerance}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Investment Goals <span className="text-red-500">*</span>
                  <span className="text-gray-400 font-normal"> (select all that apply)</span>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { value: 'growth', label: 'Long-term Growth' },
                    { value: 'income', label: 'Passive Income' },
                    { value: 'retirement', label: 'Retirement Savings' },
                    { value: 'short_term', label: 'Short-term Gains' },
                    { value: 'diversification', label: 'Diversification' },
                    { value: 'learning', label: 'Learn Trading' },
                  ].map((option) => (
                    <button
                      key={option.value}
                      onClick={() => {
                        const goals = preferences.investment_goals || []
                        const newGoals = goals.includes(option.value)
                          ? goals.filter((g) => g !== option.value)
                          : [...goals, option.value]
                        setPreferences({ ...preferences, investment_goals: newGoals })
                        if (errors.investment_goals) setErrors({ ...errors, investment_goals: '' })
                      }}
                      className={`p-3 rounded-lg border-2 text-left transition-all ${
                        preferences.investment_goals?.includes(option.value)
                          ? 'border-blue-500 bg-blue-50'
                          : errors.investment_goals
                          ? 'border-red-300 hover:border-red-400'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="font-medium text-gray-900 flex items-center gap-2">
                        {preferences.investment_goals?.includes(option.value) && (
                          <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                        {option.label}
                      </div>
                    </button>
                  ))}
                </div>
                {errors.investment_goals && (
                  <p className="mt-2 text-sm text-red-500">{errors.investment_goals}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Initial Investment Range <span className="text-red-500">*</span>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { value: '0-1000', label: 'Under $1,000' },
                    { value: '1000-5000', label: '$1,000 - $5,000' },
                    { value: '5000-25000', label: '$5,000 - $25,000' },
                    { value: '25000-100000', label: '$25,000 - $100,000' },
                    { value: '100000+', label: '$100,000+' },
                  ].map((option) => (
                    <button
                      key={option.value}
                      onClick={() => {
                        setPreferences({ ...preferences, initial_investment_range: option.value })
                        if (errors.initial_investment_range) setErrors({ ...errors, initial_investment_range: '' })
                      }}
                      className={`p-3 rounded-lg border-2 text-left transition-all ${
                        preferences.initial_investment_range === option.value
                          ? 'border-blue-500 bg-blue-50'
                          : errors.initial_investment_range
                          ? 'border-red-300 hover:border-red-400'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="font-medium text-gray-900">{option.label}</div>
                    </button>
                  ))}
                </div>
                {errors.initial_investment_range && (
                  <p className="mt-2 text-sm text-red-500">{errors.initial_investment_range}</p>
                )}
              </div>
            </div>
          )}

          {/* Step 3: Brokerage */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <p className="text-gray-600">
                Connect your brokerage account to enable automated trading. This step is optional - you can always connect later.
              </p>
              <BrokerageConnect
                userId={userId || ''}
                onConnectionChange={(hasConnection) => {
                  // Update completedSteps when brokerage connection changes
                  if (hasConnection && !completedSteps.includes(3)) {
                    setCompletedSteps([...completedSteps, 3])
                  } else if (!hasConnection && completedSteps.includes(3)) {
                    setCompletedSteps(completedSteps.filter(s => s !== 3))
                  }
                }}
              />
            </div>
          )}

          {/* Step 4: Watchlist */}
          {currentStep === 4 && (
            <div className="space-y-6">
              <p className="text-gray-600">
                Search and add stocks you're interested in tracking. This step is optional - you can always modify your watchlist later.
              </p>
              <StockSearch
                userId={userId || ''}
                watchlist={watchlist}
                onWatchlistUpdate={handleWatchlistUpdate}
              />
            </div>
          )}

          {/* Navigation Buttons */}
          <div className="flex justify-between mt-10 pt-6 border-t border-gray-200">
            <button
              onClick={handleBack}
              disabled={currentStep === 0}
              className="px-6 py-3 text-gray-700 font-medium rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Back
            </button>
            {currentStep < STEPS.length - 1 ? (
              <button
                onClick={handleSaveStep}
                disabled={isSaving}
                className="px-8 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                {isSaving ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Saving...
                  </>
                ) : (
                  <>
                    Save & Continue
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </>
                )}
              </button>
            ) : (
              <button
                onClick={handleComplete}
                disabled={isSaving}
                className="px-8 py-3 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                {isSaving ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Completing...
                  </>
                ) : (
                  <>
                    Complete Setup
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        {/* Skip Option */}
        <div className="text-center mt-6">
          <button
            onClick={handleComplete}
            className="text-sm text-gray-500 hover:text-gray-700 underline"
          >
            Skip for now, I'll complete this later
          </button>
        </div>
      </div>
    </div>
  )
}
