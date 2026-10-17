import { defineConfig } from 'vite';
import tsconfigPaths from 'vite-tsconfig-paths';
import react from '@vitejs/plugin-react-swc';
import mkcert from 'vite-plugin-mkcert';
import tailwindcss from '@tailwindcss/vite';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production';

  return {
    base: '/SpaceHunter',
    build: {
      // demo-only: allow top-level await (mockEnv) in the bundle
      target: 'esnext',
    },
    plugins: [
      tailwindcss(),
      react(),
      tsconfigPaths(),
      process.env.HTTPS && mkcert(),
    ],
    publicDir: './public',
    server: {
      host: true,
      allowedHosts: ['.pinggy-free.link', '.pinggy.net', '.loca.lt', '.trycloudflare.com'],
      // Прокси используется только в режиме разработки
      proxy: !isProduction
        ? {
            '/api': {
              target: 'http://localhost:8000',
              changeOrigin: true,
              secure: false,
              headers: {
                'Cache-Control': 'no-cache',
              },
            },
          }
        : undefined,
    },
  };
});