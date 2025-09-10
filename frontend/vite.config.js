import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',  // Bind to all interfaces for tunnel access
    port: 5173,  // Use a different port that VS Code might recognize better
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        timeout: 30000, // 30秒超时
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('WebSocket proxy error:', err);
          });
          proxy.on('proxyReqWs', (_proxyReq, _req, socket) => {
            socket.setTimeout(30000); // 设置socket超时
            socket.on('error', (err) => {
              console.log('WebSocket socket error:', err);
            });
            socket.on('timeout', () => {
              console.log('WebSocket socket timeout');
              socket.destroy();
            });
          });
          proxy.on('close', () => {
            console.log('WebSocket proxy closed');
          });
        }
      }
    }
  }
})
