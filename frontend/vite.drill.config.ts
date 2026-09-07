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
    // The deploy script overrides this with a staging directory so a failed
    // build can never empty the live Drill bundle.
    outDir: process.env.TIME_TRACKER_DRILL_VITE_OUT_DIR || resolve(projectDir, 'drill-dist'),
    emptyOutDir: true,
    sourcemap: false,
    cssCodeSplit: true,
    chunkSizeWarningLimit: 500,
  },
})
