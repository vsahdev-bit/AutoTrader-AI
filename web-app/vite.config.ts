import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
  // Load .env file variables
  const env = loadEnv(mode, process.cwd(), '')
  
  // For Docker: prefer runtime env var (process.env.VITE_API_URL) 
  // For local dev: fall back to .env file or localhost
  const apiUrl = process.env.VITE_API_URL || env.VITE_API_URL || 'http://localhost:3001'
  
  // Recommendation engine URL for regime endpoint
  const recommendationEngineUrl = process.env.VITE_RECOMMENDATION_ENGINE_URL || env.VITE_RECOMMENDATION_ENGINE_URL || 'http://localhost:8000'
  
  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: apiUrl,
          changeOrigin: true,
        },
        '/regime': {
          target: recommendationEngineUrl,
          changeOrigin: true,
        }
      }
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
  }
})
