import { realpathSync } from 'node:fs'
import path from 'path'
import { defineConfig, searchForWorkspaceRoot, type PluginOption } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig(() => {
  const plugins: PluginOption[] = [react(), tailwindcss()]
  const backendUrl = process.env.VITE_BACKEND_URL ?? 'http://localhost:8000'
  const dependencyRoot = realpathSync(path.resolve(__dirname, 'node_modules'))

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
      fs: {
        // Worktrees may reuse the canonical checkout's node_modules through a
        // symlink. Vite resolves font assets to that real path before applying
        // its filesystem allow-list.
        allow: [searchForWorkspaceRoot(process.cwd()), dependencyRoot],
      },
      proxy: {
        '/api': backendUrl,
        '/covers': backendUrl,
      },
    },
  }
})
