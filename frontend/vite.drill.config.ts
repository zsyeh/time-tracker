import { resolve } from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const projectDir = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  root: resolve(projectDir, 'drill'),
  plugins: [vue()],
  base: '/static/drill/',
  build: {
    outDir: resolve(projectDir, 'drill-dist'),
    emptyOutDir: true,
    sourcemap: false,
    cssCodeSplit: true,
    chunkSizeWarningLimit: 500,
  },
})

