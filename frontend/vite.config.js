import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 화면은 같은 출처의 /api로만 요청한다. 개발 서버에서는 backend(8080)로 넘긴다.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: { '/api': { target: process.env.BACKEND_URL || 'http://localhost:8080', changeOrigin: false } },
  },
  test: { environment: 'jsdom', globals: true },
})
