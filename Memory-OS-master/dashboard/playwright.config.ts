import { defineConfig, devices } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8001";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: require.resolve("./e2e/global-setup.ts"),
  timeout: 60_000,
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    storageState: "e2e/.auth/user.json",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      testIgnore: /auth\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "auth-flow",
      testMatch: /auth\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], storageState: { cookies: [], origins: [] } },
    },
  ],
  webServer: process.env.CI
    ? undefined
    : [
        {
          command: "python -m uvicorn app.main:app --port 8001",
          cwd: "../services/api",
          url: `${API_URL}/v1/health`,
          reuseExistingServer: false,
          timeout: 120_000,
          env: {
            PYTHONPATH: ".",
            DATABASE_URL: "sqlite+aiosqlite:///./e2e_api.db",
            MEMORY_OS_ALLOW_ANON: "true",
            EMBEDDING_DIM: "4",
          },
        },
        {
          command: "npm run dev",
          url: "http://localhost:3000",
          reuseExistingServer: false,
          timeout: 120_000,
          env: {
            NEXT_PUBLIC_MEMORY_OS_API_URL: API_URL,
          },
        },
      ],
});
