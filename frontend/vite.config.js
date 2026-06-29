import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        // 确保 SSE 流式响应不被缓冲 — 对于 text/event-stream 立即转发每个 chunk
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes, req, res) => {
            // 对于 SSE 流，禁用代理层的缓冲，确保逐 chunk 转发
            if (proxyRes.headers['content-type'] &&
                proxyRes.headers['content-type'].includes('text/event-stream')) {
              // 设置 Node.js 层面的 raw 响应刷新
              if (res.flushHeaders) res.flushHeaders()
            }
          })
        },
      },
    },
  },
})
