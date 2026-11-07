import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { visualizer } from 'rollup-plugin-visualizer'

const apiTarget = process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), ...(process.env.ANALYZE === '1' ? [visualizer({ filename: 'dist/stats.html', gzipSize: true })] : [])],
  server: {
    proxy: {
      '/api': { target: apiTarget, changeOrigin: false },
      '/media': { target: apiTarget, changeOrigin: false },
    },
    watch: {
      usePolling: process.env.VITE_USE_POLLING === '1',
    },
  },
})
