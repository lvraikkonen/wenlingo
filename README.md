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

# Optional: seed one disposable default child for V0.4 assessment verification.
# This keeps the four demo children unchanged, and creates a new all-40 child
# that should start from the "入门小试炼" dashboard recommendation.
$seed = @'
from sqlmodel import Session, create_engine

from app.domain.enums import StudentPersona
from app.domain.models import AbilityProfile, StudentProfile
from app.domain.seed import seed_demo_data

engine = create_engine("sqlite:///./manual-test.db")
with Session(engine) as session:
    seed_demo_data(session)
    if session.get(StudentProfile, "manual-default-child") is None:
        student = StudentProfile(
            id="manual-default-child",
            parent_id="p1",
            name="小测",
            persona=StudentPersona.real_child,
            is_real_child=True,
        )
        session.add(student)
        session.add(AbilityProfile(student_id=student.id))
        session.commit()
'@
$seed | uv run python -

uv run uvicorn app.main:app --host 127.0.0.1 --port 8012
```

Terminal 2:

```powershell
cd apps/web
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8012"
corepack pnpm dev --hostname 127.0.0.1 --port 3012
```

Open `http://127.0.0.1:3012` and use the demo family entry. For V0.4
assessment verification, choose `小测`: before completing the entry trial its
Dashboard should recommend `入门小试炼`; after completion it should show
`第一张能力草图` and switch the main recommendation to a personalized sentence or
essay task. If you want real LLM feedback in this mode, configure
`apps/api/.env` as described below before starting the API.

## Local Real LLM Check

The default provider is mock. To run one local real-LLM quality check with the
Local Development API workflow, copy the repo-root `.env-sample` to
`apps/api/.env` and fill these values:

```text
LLM_PROVIDER=http
LLM_API_KEY=your-local-test-key
LLM_MODEL=your-test-model
LLM_BASE_URL=https://your-provider.example/v1
```

Leave `LLM_PROMPT_VERSION` unset so task wrappers use Prompt Registry versions;
only set it for explicit prompt-version logging/testing overrides.

Do not commit `.env`. After running the 小宇 essay revision path, create a QA
record under `qa/` with provider/model, prompt version, whether retry/fallback
triggered, and the manual AI quality verdict.

## Environment Variables

The full environment variable checklist lives in `docs/env-vars.md`. Use it
before every Railway Dev, staging, or production config change.

Common variables that are easy to miss during Alpha QA:

- `NEXT_PUBLIC_API_BASE_URL` is set on `wenlingo-web` before build and requires
  a web redeploy when changed.
- `CORS_ALLOW_ORIGINS` and `AUTH_ALLOWED_ORIGINS` are set on `wenlingo-api`,
  must use full web HTTPS origins with no trailing slash, and require an API
  restart/redeploy when changed.
- `AUTH_SECRET_PEPPER` must be stable once Magic Code sessions are in use.
- `MAGIC_CODE_EMAIL_PROVIDER`, `MAGIC_CODE_FROM_EMAIL`, and provider secrets
  such as `RESEND_API_KEY` are API-only values.
- `MAGIC_CODE_DEV_ECHO=true` is only for internal QA in
  `ENVIRONMENT=development`; real email QA should use `MAGIC_CODE_DEV_ECHO=false`.
- `LLM_DAILY_LIMIT_ENABLED=true` is required before Daily limit QA can trigger
  the V0.5b sentence challenge rest message.
- `SENTENCE_CHALLENGE_DAILY_LIMIT_PER_STUDENT` and
  `SENTENCE_FEEDBACK_DAILY_LIMIT_PER_STUDENT` control V0.5b sentence limits
  once daily limits are enabled.

## Railway Alpha Deployment

The V0.4.1a Alpha deployment target is Railway. Use one Railway project with
three services:

```text
wenlingo-postgres  Railway PostgreSQL service
wenlingo-api       FastAPI backend, root directory apps/api
wenlingo-web       Next.js frontend, root directory apps/web
```

For Alpha, use Railway PostgreSQL or another persistent PostgreSQL instance.
Do not use local SQLite, a disposable demo database, or a database file tied to
a developer machine.

Backend service:

```text
Root Directory: apps/api
First deployment bootstrap command: uv run python -m app.db.init_db && uv run alembic stamp head
Ongoing Pre-deploy Command: uv run alembic upgrade head
Start Command: uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The current migration chain assumes the base schema already exists. On a brand-new Railway database, run the bootstrap command once to create the SQLModel schema and mark the Alembic revision as current. After that first successful deploy, switch Railway's Pre-deploy Command to the ongoing `alembic upgrade head` command. If `init_db` already ran and a later deploy fails with duplicate tables, columns, or constraints, run `uv run alembic stamp head` once to recover the missing Alembic version marker, then redeploy with the ongoing command. Do not run demo seed scripts in Alpha.

Set `DATABASE_URL` from the PostgreSQL service, `CORS_ALLOW_ORIGINS` to the
public web origin, and keep all LLM provider credentials server-side on the API
service. Keep migrations in Railway's Pre-deploy Command so normal restarts and
future scaling do not re-run migrations during application boot. Railway public
services must listen on `0.0.0.0:$PORT`, which is why the backend command binds
uvicorn explicitly.

Frontend service:

```text
Root Directory: apps/web
Build Command: corepack pnpm install --frozen-lockfile && corepack pnpm build
Start Command: corepack pnpm exec next start -H 0.0.0.0 -p $PORT
```

Set `NEXT_PUBLIC_API_BASE_URL` to the public API origin before building the web
service, because Next.js embeds `NEXT_PUBLIC_*` values into the browser bundle.
Use full HTTPS origins with no trailing slash for both `CORS_ALLOW_ORIGINS` and
`NEXT_PUBLIC_API_BASE_URL`. If either value changes, manually redeploy the
affected Railway service so CORS and the browser bundle use the new origin. Do
not expose LLM keys through `NEXT_PUBLIC_*`.

Full Alpha deployment steps, Alpha data verification, smoke tests, rollback, and
backup/deletion notes live in `docs/alpha-deploy.md`. Manual rollout QA lives in
`qa/2026-05-25-v0.4.1a-alpha-entry-manual-qa.md`.

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
