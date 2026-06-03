import { defineConfig, devices } from "@playwright/test";

const apiPort = Number(process.env.PLAYWRIGHT_API_PORT ?? 8000);
const webPort = Number(process.env.PLAYWRIGHT_WEB_PORT ?? 3000);
const apiBaseURL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? `http://127.0.0.1:${apiPort}`;
const webBaseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${webPort}`;
const webOrigin = new URL(webBaseURL).origin;
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER === "1";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: webBaseURL,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: `uv run python -m app.db.init_db && uv run python -m app.db.seed_playwright_alpha && uv run uvicorn app.main:app --host 127.0.0.1 --port ${apiPort}`,
      cwd: "../api",
      env: {
        DATABASE_URL: process.env.PLAYWRIGHT_DATABASE_URL ?? "sqlite:///./playwright-e2e.db",
        CORS_ALLOW_ORIGINS: webOrigin,
        AUTH_REQUIRED_FOR_ALPHA: "true",
        AUTH_SECRET_PEPPER: "test-pepper",
        AUTH_SESSION_COOKIE_SECURE: "false",
        LLM_PROVIDER: "mock",
        MAGIC_CODE_DEV_ECHO: "true",
      },
      url: `${apiBaseURL}/health`,
      reuseExistingServer,
      timeout: 120_000,
    },
    {
      command: `corepack pnpm dev --hostname 127.0.0.1 --port ${webPort}`,
      env: {
        NEXT_PUBLIC_API_BASE_URL: apiBaseURL,
      },
      url: webBaseURL,
      reuseExistingServer,
      timeout: 120_000,
    },
  ],
});
