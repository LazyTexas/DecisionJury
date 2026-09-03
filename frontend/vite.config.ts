import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 业务接口：/api/* → 后端（routers prefix="/api"）
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // 认证接口：后端 auth router prefix="/auth"（无 /api 前缀）
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
