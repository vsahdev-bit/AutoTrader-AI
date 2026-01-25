import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { AuthProvider, useAuth } from './context/AuthContext'
import { GOOGLE_CLIENT_ID } from './config/google'
import Dashboard from './pages/Dashboard'
import Home from './pages/Home'
import Onboarding from './pages/Onboarding'
import StockRecommendations from './pages/StockRecommendations'
import Connectors from './pages/Connectors'
// Public pages
import Pricing from './pages/Pricing'
import FAQ from './pages/FAQ'
import Terms from './pages/legal/Terms'
import Privacy from './pages/legal/Privacy'
import RiskDisclosure from './pages/legal/RiskDisclosure'

const queryClient = new QueryClient()

// Loading spinner component
function LoadingSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
    </div>
  )
}

// Dashboard route - only accessible if onboarding is 100% complete
function DashboardRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <LoadingSpinner />
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />
  }

  // Users with incomplete onboarding can still access dashboard (via skip)
  // The dashboard will show onboarding status card to encourage completion
  return <>{children}</>
}

// Onboarding route - accessible to all authenticated users
// Users can always access onboarding to edit their profile/preferences
function OnboardingRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <LoadingSpinner />
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

function AppRoutes() {
  return (
    <Router>
      <Routes>
        {/* Public route */}
        <Route path="/" element={<Home />} />
        
        {/* Public marketing pages */}
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/faq" element={<FAQ />} />
        
        {/* Legal pages */}
        <Route path="/terms" element={<Terms />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/risk-disclosure" element={<RiskDisclosure />} />
        
        {/* Stock Recommendations - public route for viewing recommendation history */}
        <Route path="/recommendations" element={<StockRecommendations />} />
        <Route path="/recommendations/:symbol" element={<StockRecommendations />} />
        
        {/* Connectors - public route for viewing data connector status */}
        <Route path="/connectors" element={<Connectors />} />
        
        {/* Onboarding route - protected, but accessible only if onboarding not complete */}
        <Route
          path="/onboarding"
          element={
            <OnboardingRoute>
              <Onboarding />
            </OnboardingRoute>
          }
        />
        
        {/* Dashboard - protected, accessible via skip or after completion */}
        <Route
          path="/dashboard"
          element={
            <DashboardRoute>
              <Dashboard />
            </DashboardRoute>
          }
        />

        {/* Catch all - redirect to home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  )
}

function App() {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </QueryClientProvider>
    </GoogleOAuthProvider>
  )
}

export default App
