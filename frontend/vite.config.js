import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 60001,
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:60000',
        changeOrigin: true,
      }
    }
  }
});
