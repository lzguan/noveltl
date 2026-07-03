import { defineConfig, devices } from "@playwright/test";

const frontendUrl = process.env.E2E_BASE_URL ?? "http://localhost:5173";
const backendUrl = process.env.E2E_API_URL ?? "http://127.0.0.1:8001";
const frontendBackendUrl = process.env.VITE_BACKEND_URL ?? backendUrl;
const dbUrl = process.env.E2E_DB_URL ?? process.env.TEST_URL ?? "";
const redisHost = process.env.E2E_REDIS_HOST ?? "test_redis";
const redisPort = process.env.E2E_REDIS_PORT ?? "6379";
const secretKey = process.env.SECRET_KEY ?? "e2e-secret";

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results",
  globalSetup: "./global-setup",
  /* Run tests in files in parallel */
  fullyParallel: false,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: 1,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: "html",
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('')`. */
    baseURL: frontendUrl,

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: "on-first-retry",
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },

    /* Test against mobile viewports. */
    // {
    //   name: 'Mobile Chrome',
    //   use: { ...devices['Pixel 5'] },
    // },
    // {
    //   name: 'Mobile Safari',
    //   use: { ...devices['iPhone 12'] },
    // },

    /* Test against branded browsers. */
    // {
    //   name: 'Microsoft Edge',
    //   use: { ...devices['Desktop Edge'], channel: 'msedge' },
    // },
    // {
    //   name: 'Google Chrome',
    //   use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    // },
  ],

  /* Run your local dev server before starting the tests */
  webServer: [
    {
      command: "uv --directory ../backend run uvicorn src.main:app --host 0.0.0.0 --port 8001",
      env: {
        ...process.env,
        DB_URL: dbUrl,
        DB_HOST: process.env.E2E_DB_HOST ?? process.env.TEST_HOST ?? "test_db",
        DB_USER: process.env.E2E_DB_USER ?? process.env.TEST_USER ?? "",
        DB_PASSWORD: process.env.E2E_DB_PASSWORD ?? process.env.TEST_PASSWORD ?? "",
        DB_NAME: process.env.E2E_DB_NAME ?? process.env.TEST_NAME ?? "",
        REDIS_HOST: redisHost,
        REDIS_PORT: redisPort,
        SECRET_KEY: secretKey,
      },
      url: new URL("/openapi.json", backendUrl).toString(),
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "pnpm --dir ../frontend dev --host 0.0.0.0",
      env: {
        ...process.env,
        VITE_BACKEND_URL: frontendBackendUrl,
      },
      url: frontendUrl,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
