import path from 'path'
import { defineConfig, type PluginOption } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig(() => {
  const plugins: PluginOption[] = [react(), tailwindcss()]
  const backendUrl = process.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

  if (process.env.ANALYZE === 'true') {
    plugins.push(
      visualizer({
        filename: 'dist/stats.html',
        open: true,
        gzipSize: true,
        brotliSize: true,
      }) as PluginOption,
    )
  }

  return {
    plugins,
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      allowedHosts: true as const,
      proxy: {
        '/api': backendUrl,
        '/covers': backendUrl,
      },
    },
  }
})
