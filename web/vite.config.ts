import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const bridge = process.env.PDA_BRIDGE_URL ?? 'http://127.0.0.1:47615'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    host: '0.0.0.0',
    port: 47616,
    proxy: { '/api': { target: bridge, changeOrigin: false } },
  },
  test: {
    environment: 'node',
  },
})
