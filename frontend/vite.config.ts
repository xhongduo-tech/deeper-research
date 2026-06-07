import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import legacy from '@vitejs/plugin-legacy'

const legacyBrowserTargets = [
  'Chrome >= 58',
  'Edge >= 18',
  'Firefox >= 57',
  'Safari >= 11',
  'iOS >= 11',
]

function figmaAssetResolver() {
  return {
    name: 'figma-asset-resolver',
    resolveId(id) {
      if (id.startsWith('figma:asset/')) {
        const filename = id.replace('figma:asset/', '')
        return path.resolve(__dirname, 'src/assets', filename)
      }
    },
  }
}

export default defineConfig({
  plugins: [
    figmaAssetResolver(),
    // The React and Tailwind plugins are both required for Make, even if
    // Tailwind is not being actively used – do not remove them
    react(),
    tailwindcss(),
    legacy({
      targets: legacyBrowserTargets,
      modernTargets: legacyBrowserTargets,
      modernPolyfills: true,
      renderLegacyChunks: true,
    }),
  ],
  build: {
    cssTarget: ['chrome58', 'firefox57', 'safari11', 'edge18'],
  },
  resolve: {
    alias: {
      // Alias @ to the src directory
      '@': path.resolve(__dirname, './src'),
    },
  },

  // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
  assetsInclude: ['**/*.svg', '**/*.csv'],
})
