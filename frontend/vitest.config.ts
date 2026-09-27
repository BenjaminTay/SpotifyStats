import path from 'path'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    css: false,
    // Keep the full suite deterministic on shared developer machines. The
    // default CPU-sized pool can starve jsdom timers when other verification
    // jobs are active, producing unrelated 5 s interaction timeouts.
    maxWorkers: 2,
  },
})
