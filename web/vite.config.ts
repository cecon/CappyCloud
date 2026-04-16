import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  /** Com `npm run dev`, o proxy encaminha `/api` para a FastAPI no host (ex.: Docker `API_PORT` 38000). */
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget =
    env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:38000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: true,
      watch: {
        ignored: ['**/.pnpm-store/**'],
      },
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/health': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
