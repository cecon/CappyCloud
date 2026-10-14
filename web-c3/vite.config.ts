import path from 'node:path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// Servido em /c3/ ao lado do frontend atual até a virada (specs/013-c3theme-frontend).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:38000';
  const legacySrc = path.resolve(import.meta.dirname, '../web/src');

  return {
    base: '/c3/',
    plugins: [react()],
    resolve: {
      tsconfigPaths: true,
      // A camada de dados do web/ importa a si mesma por '@/...'.
      alias: [
        { find: /^@cappy\//, replacement: `${legacySrc}/` },
        { find: /^@\//, replacement: `${legacySrc}/` }
      ]
    },
    server: {
      port: 5175,
      host: true,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        '/health': { target: apiTarget, changeOrigin: true }
      }
    },
    test: {
      environment: 'jsdom'
    }
  };
});
