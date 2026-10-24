import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests/e2e',
  testIgnore: '**/api.spec.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  use: {
    baseURL: 'http://127.0.0.1:32146',
    viewport: { width: 1440, height: 1040 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'node scripts/test-host.mjs',
      url: 'http://127.0.0.1:32146/api/health',
      reuseExistingServer: false,
      timeout: 45000,
    },
    {
      command: 'node scripts/test-host.mjs --live',
      url: 'http://127.0.0.1:32147/api/health',
      reuseExistingServer: false,
      timeout: 45000,
    },
  ],
})
