// frontend/vite.config.js
import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    proxy: {
      // 将所有 /api 开头的请求代理到后端 FastAPI 服务器
      '/api': {
        target: 'http://127.0.0.1:8000', // 后端地址
        changeOrigin: true, // 对于虚拟主机站点是必需的
        // 通常不需要重写路径，因为我们的 API 路径也是 /api/...
        // rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
});