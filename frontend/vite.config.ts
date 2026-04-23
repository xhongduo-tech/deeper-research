import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import legacy from '@vitejs/plugin-legacy'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    // Generate legacy bundles for old browsers commonly found inside
    // enterprise/intranet environments (IE 11, old Edge, Chrome <= 70,
    // Safari <= 11, Android WebView 4.x). Modern browsers still load the
    // ES module build; only legacy browsers fall back to the nomodule
    // polyfilled bundle, so there is no cost for modern users.
    legacy({
      targets: [
        'defaults',
        'chrome >= 61',
        'safari >= 11',
        'firefox >= 60',
        'edge >= 79',
        'ie >= 11',
      ],
      additionalLegacyPolyfills: ['regenerator-runtime/runtime'],
      modernPolyfills: true,
      renderLegacyChunks: true,
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    // `target` is managed by @vitejs/plugin-legacy above. We only keep
    // a conservative cssTarget so autoprefixer/esbuild produce CSS
    // compatible with the oldest browsers we support.
    cssTarget: ['chrome61', 'safari11', 'edge79'],
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'query-vendor': ['@tanstack/react-query', 'axios'],
          'ui-vendor': ['framer-motion', 'lucide-react', 'react-hot-toast'],
          'chart-vendor': ['recharts'],
          'editor-vendor': ['@uiw/react-md-editor'],
          'state-vendor': ['zustand'],
        },
      },
    },
    assetsInlineLimit: 4096,
    sourcemap: false,
    minify: 'esbuild',
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: process.env.VITE_WS_URL || 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version),
  },
})
