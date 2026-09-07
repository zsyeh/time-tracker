import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/static/app/',
  build: {
    // Native deployment builds into a staging directory first. Keeping the
    // default makes local `npm run build` behaviour unchanged.
    outDir: process.env.TIME_TRACKER_VITE_OUT_DIR || 'dist',
    emptyOutDir: true,
    sourcemap: false,
    cssCodeSplit: true,
    chunkSizeWarningLimit: 700,
  },
})
