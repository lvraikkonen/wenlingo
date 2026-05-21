# Wenlingo 小文星球

Wenlingo（小文星球）是一个 AI 驱动的中文语文阅读与写作成长平台，面向小学阶段孩子，围绕阅读理解、作文写作、能力诊断与游戏化成长，提供个性化练习、智能反馈和持续进步追踪。

Wenlingo is an AI-powered Chinese literacy platform for children, designed to improve reading comprehension and writing skills through personalized practice, intelligent feedback, and gamified growth journeys.

## Local Development

### PostgreSQL-backed startup

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

### Temporary SQLite startup

Use this path for quick local manual testing when PostgreSQL is unavailable or
when you want a disposable database.

Terminal 1:

```powershell
cd apps/api
$env:DATABASE_URL = "sqlite:///./manual-test.db"
$env:CORS_ALLOW_ORIGINS = "http://127.0.0.1:3012,http://localhost:3012"
uv run python -m app.db.init_db
uv run uvicorn app.main:app --host 127.0.0.1 --port 8012
```

Terminal 2:

```powershell
cd apps/web
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8012"
corepack pnpm dev --hostname 127.0.0.1 --port 3012
```

Open `http://127.0.0.1:3012` and use the demo family entry. If you want real
LLM feedback in this mode, configure `apps/api/.env` as described below before
starting the API.

## Local Real LLM Check

The default provider is mock. To run one local real-LLM quality check with the
Local Development API workflow, copy the repo-root `.env-sample` to
`apps/api/.env` and fill these values:

```text
LLM_PROVIDER=http
LLM_API_KEY=your-local-test-key
LLM_MODEL=your-test-model
LLM_BASE_URL=https://your-provider.example/v1
LLM_PROMPT_VERSION=v0.2-quality-spine-2026-05-14
```

Do not commit `.env`. After running the 小宇 essay revision path, create a QA
record under `qa/` with provider/model, prompt version, whether retry/fallback
triggered, and the manual AI quality verdict.

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
`PLAYWRIGHT_DATABASE_URL` to point it at another database. Remove stale SQLite
files before E2E runs using `qa/2026-05-21-stale-sqlite-cleanup.md`. Use
`corepack pnpm e2e -- mvp.spec.ts` on Windows if `pnpm` is not on PATH.
