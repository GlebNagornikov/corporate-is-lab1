import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173'
const usesDevServer = baseURL.startsWith('http:')

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  retries: 0,
  // Vite transforms modules on demand, including after a hard navigation.
  timeout: usesDevServer ? 90_000 : 60_000,
  expect: { timeout: usesDevServer ? 15_000 : 5_000 },
  reporter: 'list',
  use: {
    baseURL,
    ignoreHTTPSErrors: true,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
