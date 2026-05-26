# WenLingo Alpha Deployment Runbook

Date: 2026-05-25

## Purpose

Deploy V0.4.1a for 3-5 trusted Alpha families on Railway.

## Railway Project Layout

Use one Railway project with three services:

```text
wenlingo-postgres  Railway PostgreSQL service
wenlingo-api       FastAPI backend service, root directory apps/api
wenlingo-web       Next.js frontend service, root directory apps/web
```

The Alpha environment must use Railway PostgreSQL or another persistent PostgreSQL instance. Do not use local SQLite, a disposable demo database, or a database file tied to a developer machine.

Railway public services must listen on `0.0.0.0:$PORT`. The backend start command below binds uvicorn to `0.0.0.0` and Railway's `PORT`; the frontend start command passes the same host and port through to Next.js.

## Architecture

```text
Browser
-> Railway wenlingo-web public domain
-> Railway wenlingo-api public domain
-> Railway wenlingo-postgres persistent PostgreSQL
-> server-side LLM provider
```

## Railway Services

### PostgreSQL

Create a Railway PostgreSQL service first. Use its `DATABASE_URL` for the backend service.

### Backend Service

Service:

```text
Name: wenlingo-api
Source: GitHub repo
Root Directory: apps/api
Pre-deploy Command: uv run alembic upgrade head
Start Command: uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
Public Networking: enabled
```

Keep database migrations in Railway's Pre-deploy Command instead of the long-running Start Command. This prevents routine container restarts, retries, or future scaling from re-running migrations as part of application boot.

Backend variables:

| Variable | Railway value |
| --- | --- |
| `DATABASE_URL` | Reference the PostgreSQL service `DATABASE_URL` from Railway's variable reference picker. |
| `CORS_ALLOW_ORIGINS` | The generated public HTTPS origin for `wenlingo-web` after Public Networking is enabled, with no trailing slash. |
| `LLM_PROVIDER` | `http` |
| `LLM_API_KEY` | The server-side key from the selected LLM provider account. |
| `LLM_MODEL` | The model name selected for Alpha. |
| `LLM_BASE_URL` | The base URL from the selected LLM provider. |
| `LLM_PROMPT_VERSION` | `v0.2-quality-spine-2026-05-14` |

Use a full HTTPS origin for `CORS_ALLOW_ORIGINS`, for example:

```text
https://wenlingo-web-production.up.railway.app
```

Bad value with trailing slash:

```text
https://wenlingo-web-production.up.railway.app/
```

### Frontend Service

Service:

```text
Name: wenlingo-web
Source: GitHub repo
Root Directory: apps/web
Build Command: corepack pnpm install --frozen-lockfile && corepack pnpm build
Start Command: corepack pnpm start -- -H 0.0.0.0 -p $PORT
Public Networking: enabled
```

`apps/web/package.json` defines `start` as `next start`. The Railway Start Command passes `-H 0.0.0.0 -p $PORT` through pnpm so the Next.js service binds to Railway's public host and port.

Frontend variables:

| Variable | Railway value |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | The generated public HTTPS origin for `wenlingo-api` after Public Networking is enabled, with no trailing slash. |

Set `NEXT_PUBLIC_API_BASE_URL` before building the frontend service because Next.js bakes `NEXT_PUBLIC_*` variables into the browser bundle at build time.

On first deployment, set `CORS_ALLOW_ORIGINS` after the web public domain exists, then redeploy `wenlingo-api`. Set `NEXT_PUBLIC_API_BASE_URL` before building `wenlingo-web`. If either `NEXT_PUBLIC_API_BASE_URL` or `CORS_ALLOW_ORIGINS` changes later, manually redeploy the affected service so the runtime CORS allowlist and browser bundle use the new values.

Use a full HTTPS origin for `NEXT_PUBLIC_API_BASE_URL`, for example:

```text
https://wenlingo-api-production.up.railway.app
```

Do not include a trailing slash or path.

LLM keys must remain server-side on `wenlingo-api`. Do not expose LLM keys through `NEXT_PUBLIC_*` variables.

## Smoke Test

- Open the `wenlingo-api` public domain plus `/health` and confirm status is ok.
- Open the `wenlingo-web` public domain plus `/alpha/start`.
- Accept Alpha notice and create a child.
- Confirm child appears in `/parent/children`.
- Enter child dashboard and confirm `入门小试炼` is recommended.
- Complete assessment with the configured LLM provider.
- Return to dashboard and confirm main recommendation changes.
- Open parent summary and confirm real counts and ability changes appear.

## Alpha Data Verification

After each invited family completes first use, verify the Alpha data loop is producing durable records:

- `ParentUser` row exists for the Alpha parent.
- `StudentProfile` row exists for the created child.
- Alpha consent or Alpha entry record exists if such a table is introduced; V0.4.1a otherwise relies on the Alpha notice plus parent and child records.
- `Assessment` row exists after the entry trial.
- Child answer records exist for sentence revision and short writing.
- `AbilityProfile` changed and `AbilityHistory` rows exist for the assessment-driven deltas.
- Parent summary reads real persisted practice counts and ability changes.
- LLM request/response metadata or provider logs are available for debugging without exposing API keys or storing secrets in browser-visible variables.

## Manual Alpha Link Distribution

Send only the hosted `wenlingo-web` public domain plus `/alpha/start` to invited trusted families. Do not publish the link publicly.

## Backup and Deletion Note

Before inviting families, confirm Railway PostgreSQL backup/export access for the Alpha database. For deletion requests during V0.4.1a, identify the relevant `ParentUser.id` or `StudentProfile.id` and delete linked Alpha data manually after exporting a backup.

## Rollback

If Alpha entry breaks, remove or hide the `/alpha/start` link and redeploy the previous working Railway deployment. Keep the PostgreSQL service intact so created Alpha rows are not lost.

Do not run downgrade migrations during Alpha rollback unless the database has been backed up and the migration impact is fully understood. During Alpha, protecting real family and child records is more important than making schema history look tidy.
