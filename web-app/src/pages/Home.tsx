import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { GoogleLogin, CredentialResponse } from '@react-oauth/google'
import { useAuth } from '../context/AuthContext'
import { isGoogleOAuthConfigured } from '../config/google'

export default function Home() {
  const navigate = useNavigate()
  const { login, isAuthenticated, isLoading, isCheckingOnboarding, isOnboardingComplete } = useAuth()
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    // Wait until auth loading AND onboarding check are complete before redirecting
    if (isAuthenticated && !isCheckingOnboarding) {
      // Redirect based on onboarding completion (100% = all sections filled)
      if (isOnboardingComplete) {
        navigate('/dashboard')
      } else {
        navigate('/onboarding')
      }
    }
  }, [isAuthenticated, isCheckingOnboarding, isOnboardingComplete, navigate])

  const handleGoogleSuccess = async (credentialResponse: CredentialResponse) => {
    try {
      setAuthError(null)
      if (credentialResponse.credential) {
        await login(credentialResponse.credential)
        // Navigation will be handled by the useEffect above after state updates
      }
    } catch (error) {
      console.error('Login failed:', error)
      const { toFriendlyAuthErrorMessage } = await import('../utils/authErrors')
      setAuthError(toFriendlyAuthErrorMessage(error))
    }
  }

  const handleGoogleError = () => {
    console.error('Google Sign-In failed')
  }

  if (isLoading || (isAuthenticated && isCheckingOnboarding)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm sticky top-0 z-50 border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <div className="flex items-center gap-2">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <span className="text-xl font-bold text-gray-900">AutoTrader AI</span>
            </div>

            {/* Navigation */}
            <nav className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-gray-600 hover:text-gray-900 font-medium">Features</a>
              <Link to="/pricing" className="text-gray-600 hover:text-gray-900 font-medium">Pricing</Link>
              <a href="#testimonials" className="text-gray-600 hover:text-gray-900 font-medium">Testimonials</a>
              <Link to="/faq" className="text-gray-600 hover:text-gray-900 font-medium">FAQ</Link>
            </nav>

            {/* CTA */}
            <div className="flex items-center gap-4">
              <a href="#login" className="hidden sm:inline-flex px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors">
                Get Started
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="pt-12 pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left Content */}
            <div>
              {/* Rating Badge */}
              <div className="inline-flex items-center gap-2 px-4 py-2 bg-white rounded-full shadow-sm border border-gray-100 mb-6">
                <div className="flex">
                  {[...Array(5)].map((_, i) => (
                    <svg key={i} className="w-4 h-4 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                  ))}
                </div>
                <span className="text-sm text-gray-600">Rated 5 stars by 2,000+ traders</span>
              </div>

              {/* Headline */}
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-gray-900 leading-tight mb-6">
                AI Trading Bot with{' '}
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">
                  ~94% Win Rate
                </span>
              </h1>

              {/* Description */}
              <p className="text-lg text-gray-600 mb-6 leading-relaxed">
                Trade stocks like a pro. Access AI-powered bots and deploy them in minutes! 
                Skip the guesswork and let AutoTrader AI trade for you intelligently.
              </p>

              <p className="text-gray-600 mb-8">
                <span className="font-medium">Latest:</span>{' '}
                <a href="#" className="text-blue-600 hover:underline">View Latest Bot Performance</a>
                {' | '}
                <a href="#pricing" className="text-blue-600 hover:underline">January 2026 Promotion!</a>
              </p>

              {/* Login Card */}
              <div id="login" className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 max-w-md">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Start Trading Now</h3>

                {authError && (
                  <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
                    {authError}
                  </div>
                )}
                
                {isGoogleOAuthConfigured() ? (
                  <div className="flex justify-center">
                    <GoogleLogin
                      onSuccess={handleGoogleSuccess}
                      onError={handleGoogleError}
                      useOneTap
                      theme="outline"
                      size="large"
                      width="320"
                      text="continue_with"
                      shape="rectangular"
                    />
                  </div>
                ) : (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
                    Google OAuth not configured. Check .env file.
                  </div>
                )}

                <p className="text-xs text-gray-500 text-center mt-4">
                  Free to start • No credit card required
                </p>
              </div>
            </div>

            {/* Right - Dashboard Preview */}
            <div className="relative">
              <div className="bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
                <div className="bg-gray-100 px-4 py-3 flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-400"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-400"></div>
                  <div className="w-3 h-3 rounded-full bg-green-400"></div>
                </div>
                <div className="p-6">
                  <DashboardPreview />
                </div>
              </div>
              {/* Floating Stats */}
              <div className="absolute -bottom-6 -left-6 bg-white rounded-xl shadow-lg border border-gray-100 p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
                    <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                    </svg>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-gray-900">+24.8%</div>
                    <div className="text-sm text-gray-500">Monthly Returns</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <FeaturesSection />

      {/* Testimonials Section */}
      <TestimonialsSection />

      {/* Footer */}
      <Footer />
    </div>
  )
}

function DashboardPreview() {
  const stocks = [
    { symbol: 'AAPL', name: 'Apple Inc.', price: 178.50, change: +2.4, signal: 'BUY' },
    { symbol: 'GOOGL', name: 'Alphabet', price: 141.25, change: -0.8, signal: 'HOLD' },
    { symbol: 'MSFT', name: 'Microsoft', price: 378.90, change: +1.2, signal: 'BUY' },
  ]

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h4 className="font-semibold text-gray-900">AI Recommendations</h4>
        <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">Live</span>
      </div>
      {stocks.map((stock) => (
        <div key={stock.symbol} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
          <div>
            <div className="font-medium text-gray-900">{stock.symbol}</div>
            <div className="text-xs text-gray-500">{stock.name}</div>
          </div>
          <div className="text-right">
            <div className="font-medium">${stock.price}</div>
            <div className={`text-xs ${stock.change > 0 ? 'text-green-600' : 'text-red-600'}`}>
              {stock.change > 0 ? '+' : ''}{stock.change}%
            </div>
          </div>
          <span className={`px-2 py-1 text-xs font-medium rounded ${
            stock.signal === 'BUY' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
          }`}>
            {stock.signal}
          </span>
        </div>
      ))}
    </div>
  )
}

function FeaturesSection() {
  const features = [
    { icon: '🤖', title: 'AI-Powered Bots', desc: 'Advanced ML algorithms analyze markets 24/7' },
    { icon: '📊', title: 'Real-time Signals', desc: 'Get instant buy/sell recommendations' },
    { icon: '🔒', title: 'Bank-grade Security', desc: 'Your data is encrypted and protected' },
    { icon: '⚡', title: 'Lightning Fast', desc: 'Execute trades in milliseconds' },
  ]

  return (
    <section id="features" className="py-20 px-4 bg-white">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">Why Choose AutoTrader AI?</h2>
          <p className="text-gray-600 max-w-2xl mx-auto">Powerful features designed to maximize your trading success</p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          {features.map((f, i) => (
            <div key={i} className="text-center p-6 rounded-2xl bg-gray-50 hover:bg-blue-50 transition-colors">
              <div className="text-4xl mb-4">{f.icon}</div>
              <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
              <p className="text-sm text-gray-600">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function TestimonialsSection() {
  const testimonials = [
    { name: 'Sarah M.', role: 'Day Trader', text: 'AutoTrader AI has transformed my trading. 95% win rate in my first month!', rating: 5 },
    { name: 'James K.', role: 'Portfolio Manager', text: 'The AI recommendations are incredibly accurate. Highly recommend!', rating: 5 },
    { name: 'Mike R.', role: 'Retail Investor', text: 'Finally, a trading bot that actually works. Great customer support too.', rating: 5 },
  ]

  return (
    <section id="testimonials" className="py-20 px-4 bg-gradient-to-b from-white to-blue-50">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-12">
          <span className="text-blue-600 font-medium">Testimonials</span>
          <h2 className="text-3xl font-bold text-gray-900 mt-2">What Our Users Say</h2>
        </div>
        <div className="grid md:grid-cols-3 gap-8">
          {testimonials.map((t, i) => (
            <div key={i} className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
              <div className="flex mb-4">
                {[...Array(t.rating)].map((_, j) => (
                  <svg key={j} className="w-5 h-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                ))}
              </div>
              <p className="text-gray-600 mb-4">"{t.text}"</p>
              <div>
                <div className="font-semibold text-gray-900">{t.name}</div>
                <div className="text-sm text-gray-500">{t.role}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="bg-gray-900 text-white">
      {/* Main Footer */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12">
          {/* Column 1: Logo & Description */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <span className="text-xl font-bold">AutoTrader AI</span>
            </div>
            <p className="text-gray-400 mb-6">
              AI Trading Bot Software.<br />Trade Intelligently.
            </p>
            <div className="mb-6">
              <p className="text-gray-500 text-sm mb-1">Need immediate support?</p>
              <a href="mailto:support@autotrader.ai" className="text-blue-400 hover:text-blue-300 transition-colors">
                support@autotrader.ai
              </a>
            </div>
            {/* Social Icons */}
            <div className="flex gap-4">
              <a href="#" className="w-10 h-10 bg-gray-800 rounded-lg flex items-center justify-center hover:bg-gray-700 transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M24 4.557c-.883.392-1.832.656-2.828.775 1.017-.609 1.798-1.574 2.165-2.724-.951.564-2.005.974-3.127 1.195-.897-.957-2.178-1.555-3.594-1.555-3.179 0-5.515 2.966-4.797 6.045-4.091-.205-7.719-2.165-10.148-5.144-1.29 2.213-.669 5.108 1.523 6.574-.806-.026-1.566-.247-2.229-.616-.054 2.281 1.581 4.415 3.949 4.89-.693.188-1.452.232-2.224.084.626 1.956 2.444 3.379 4.6 3.419-2.07 1.623-4.678 2.348-7.29 2.04 2.179 1.397 4.768 2.212 7.548 2.212 9.142 0 14.307-7.721 13.995-14.646.962-.695 1.797-1.562 2.457-2.549z"/>
                </svg>
              </a>
              <a href="#" className="w-10 h-10 bg-gray-800 rounded-lg flex items-center justify-center hover:bg-gray-700 transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
              </a>
              <a href="#" className="w-10 h-10 bg-gray-800 rounded-lg flex items-center justify-center hover:bg-gray-700 transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                </svg>
              </a>
              <a href="#" className="w-10 h-10 bg-gray-800 rounded-lg flex items-center justify-center hover:bg-gray-700 transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
              </a>
            </div>
          </div>

          {/* Column 2: Site Links */}
          <div>
            <h3 className="text-lg font-semibold mb-6">Site</h3>
            <ul className="space-y-3">
              <li><a href="#features" className="text-gray-400 hover:text-white transition-colors">Features</a></li>
              <li><Link to="/pricing" className="text-gray-400 hover:text-white transition-colors">Pricing</Link></li>
              <li><a href="#testimonials" className="text-gray-400 hover:text-white transition-colors">Testimonials</a></li>
              <li><Link to="/faq" className="text-gray-400 hover:text-white transition-colors">FAQ</Link></li>
            </ul>
          </div>

          {/* Column 3: Resources */}
          <div>
            <h3 className="text-lg font-semibold mb-6">Resources</h3>
            <ul className="space-y-3">
              <li><a href="#" className="text-gray-400 hover:text-white transition-colors">Documentation</a></li>
              <li><a href="#" className="text-gray-400 hover:text-white transition-colors">API Reference</a></li>
              <li><a href="#" className="text-gray-400 hover:text-white transition-colors">Bot Performance</a></li>
              <li><a href="#" className="text-gray-400 hover:text-white transition-colors">Trading Strategies</a></li>
              <li><a href="#" className="text-gray-400 hover:text-white transition-colors">Help Center</a></li>
              <li><a href="#" className="text-gray-400 hover:text-white transition-colors">Community</a></li>
            </ul>
          </div>

          {/* Column 4: Legal */}
          <div>
            <h3 className="text-lg font-semibold mb-6">Legal</h3>
            <ul className="space-y-3">
              <li><Link to="/terms" className="text-gray-400 hover:text-white transition-colors">Terms of Service</Link></li>
              <li><Link to="/privacy" className="text-gray-400 hover:text-white transition-colors">Privacy Policy</Link></li>
              <li><Link to="/risk-disclosure" className="text-gray-400 hover:text-white transition-colors">Risk Disclosure</Link></li>
            </ul>
            
            {/* Trust Badges */}
            <div className="mt-8">
              <p className="text-gray-500 text-sm mb-3">Trusted & Secure</p>
              <div className="flex gap-3">
                <div className="bg-gray-800 rounded-lg px-3 py-2 flex items-center gap-2">
                  <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-xs text-gray-300">SSL Secured</span>
                </div>
                <div className="bg-gray-800 rounded-lg px-3 py-2 flex items-center gap-2">
                  <svg className="w-4 h-4 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-xs text-gray-300">Verified</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-gray-500 text-sm">
              © 2026 AutoTrader AI. All rights reserved.
            </p>
            <div className="flex items-center gap-6 text-sm text-gray-500">
              <span>Made with ❤️ for traders worldwide</span>
            </div>
          </div>
        </div>
      </div>

      {/* Risk Disclaimer */}
      <div className="bg-gray-950">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-xs text-gray-600 text-center">
            <strong>Risk Disclaimer:</strong> Trading stocks, options, and cryptocurrencies involves substantial risk of loss and is not suitable for all investors. 
            Past performance does not guarantee future results. Please read our <Link to="/risk-disclosure" className="text-blue-400 hover:underline">full risk disclosure</Link> before using our services.
          </p>
        </div>
      </div>
    </footer>
  )
}
