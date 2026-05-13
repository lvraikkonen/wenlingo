# Wenlingo 小文星球

Wenlingo（小文星球）是一个 AI 驱动的中文语文阅读与写作成长平台，面向小学阶段孩子，围绕阅读理解、作文写作、能力诊断与游戏化成长，提供个性化练习、智能反馈和持续进步追踪。

Wenlingo is an AI-powered Chinese literacy platform for children, designed to improve reading comprehension and writing skills through personalized practice, intelligent feedback, and gamified growth journeys.

## Local Development

1. Start PostgreSQL:

```bash
docker compose up -d postgres postgres_test
```

2. Run the API:

```bash
cd apps/api
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000
```

3. Run the web app:

```bash
cd apps/web
pnpm install
pnpm dev
```

4. Open `http://localhost:3000` and use the demo family entry.

The API allows local browser requests from `http://localhost:3000` and
`http://127.0.0.1:3000` by default. Override `CORS_ALLOW_ORIGINS` with a
comma-separated list if you use a different local web origin.

## Verification

```bash
cd apps/api
uv run pytest -q
cd ../web
pnpm test
pnpm build
pnpm e2e
```

`pnpm e2e` starts the API and web dev servers via Playwright. By default it
uses a local SQLite file at `apps/api/playwright-e2e.db`; set
`PLAYWRIGHT_DATABASE_URL` to point it at another database. Use
`corepack pnpm e2e -- mvp.spec.ts` on Windows if `pnpm` is not on PATH.
