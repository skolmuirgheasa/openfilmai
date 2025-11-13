import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: 'frontend',
  server: {
    port: 5173,
    strictPort: true
  },
  plugins: [react()],
  build: {
    outDir: 'dist'
  }
});


