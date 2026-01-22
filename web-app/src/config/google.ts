/**
 * config/google.ts - Google OAuth Configuration
 * 
 * This module manages Google OAuth 2.0 settings for the AutoTrader AI platform.
 * Google Sign-In is the primary authentication method for users.
 * 
 * Setup Instructions:
 * 1. Go to https://console.cloud.google.com/
 * 2. Create a new project or select existing one
 * 3. Navigate to "APIs & Services" > "Credentials"
 * 4. Click "Create Credentials" > "OAuth client ID"
 * 5. Select "Web application" as application type
 * 6. Configure authorized JavaScript origins:
 *    - http://localhost:5173 (development)
 *    - https://yourdomain.com (production)
 * 7. Copy the Client ID to your .env file as VITE_GOOGLE_CLIENT_ID
 * 
 * Environment Variable:
 * - VITE_GOOGLE_CLIENT_ID: Set in .env file (not committed to git)
 * - The VITE_ prefix exposes it to the frontend (Vite convention)
 * 
 * Security Notes:
 * - Client ID is public (safe to expose in frontend code)
 * - Never expose the Client Secret (backend only)
 * - OAuth flow validates redirect URIs configured in Google Console
 * 
 * @see AuthContext.tsx for OAuth flow implementation
 * @see Home.tsx for Google Sign-In button
 */

/**
 * Google OAuth 2.0 Client ID.
 * 
 * Loaded from environment variable VITE_GOOGLE_CLIENT_ID.
 * Falls back to placeholder if not configured (shows warning in UI).
 * 
 * Usage: Passed to GoogleOAuthProvider in App.tsx
 */
export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || 'YOUR_GOOGLE_CLIENT_ID'

/**
 * Check if Google OAuth is properly configured.
 * 
 * Used to conditionally render:
 * - Google Sign-In button (if configured)
 * - Configuration warning message (if not configured)
 * 
 * @returns true if valid Client ID is set, false otherwise
 * 
 * Usage in components:
 * ```tsx
 * {isGoogleOAuthConfigured() ? (
 *   <GoogleLogin ... />
 * ) : (
 *   <div>Google OAuth not configured</div>
 * )}
 * ```
 */
export const isGoogleOAuthConfigured = () => {
  return GOOGLE_CLIENT_ID && GOOGLE_CLIENT_ID !== 'YOUR_GOOGLE_CLIENT_ID'
}
