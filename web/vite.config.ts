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
      /** Acessível em todas as interfaces (útil no Windows / preview do IDE). */
      host: true,
      /**
       * No Docker com bind mount (sobretudo Windows), o watch nativo pode falhar;
       * defina `VITE_DEV_POLLING=true` no compose de dev.
       */
      watch: env.VITE_DEV_POLLING === 'true' ? { usePolling: true } : undefined,
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
