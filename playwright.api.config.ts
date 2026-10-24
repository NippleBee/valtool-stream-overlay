import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/api.spec.ts',
  workers: 1,
  timeout: 15000,
  use: { baseURL: 'http://127.0.0.1:32149' },
  webServer: {
    command: 'node scripts/test-host.mjs --port 32149',
    url: 'http://127.0.0.1:32149/api/health',
    reuseExistingServer: false,
    timeout: 30000,
  },
})
