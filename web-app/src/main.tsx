/**
 * main.tsx - Application Entry Point
 * 
 * This is the root file that bootstraps the React application.
 * It renders the main App component into the DOM and configures
 * React's strict mode for development.
 * 
 * React StrictMode Benefits:
 * - Identifies components with unsafe lifecycles
 * - Warns about deprecated API usage
 * - Detects unexpected side effects
 * - Double-invokes certain functions to catch bugs
 * 
 * Note: StrictMode only runs in development, not production builds.
 * 
 * @see App.tsx for the main application component
 * @see index.css for global styles (Tailwind CSS)
 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// Mount the React application to the DOM
// The '!' asserts that getElementById will not return null (we know 'root' exists in index.html)
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
