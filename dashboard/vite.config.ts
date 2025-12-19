import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Base path for GitHub Pages subdirectory deployment
  // Dashboard will be accessible at: https://policyengine.github.io/crfb-tob-impacts/dashboard/
  base: '/crfb-tob-impacts/dashboard/',
})
