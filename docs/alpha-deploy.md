# WenLingo Alpha Deployment Runbook

Date: 2026-05-25

## Purpose

Deploy V0.4.1a for 3-5 trusted Alpha families on Railway, with the V0.4.1b feedback and observation addendum.

## V0.4.1b Alpha Feedback and Observation

Required env:

```text
ALPHA_ADMIN_TOKEN=<strong manual token>
```

Invite generation:

```bash
cd apps/api
uv run python -m app.ops.create_alpha_invites --count 5 --label-prefix "Alpha Family" --issued-to-note "May 2026 invited family"
```

Legacy parent binding:

```bash
uv run python -m app.ops.bind_alpha_invite --parent-id <parent-id> --code <raw-code> --note "V0.4.1a legacy family"
```

Smoke tests:

- `/alpha/start` valid invite
- `/alpha/start` consumed invite rejected
- `/parent/children` continuation for existing parent
- assessment reaction save
- summary feedback save
- `/admin/alpha` token gate
- `/admin/alpha` overview and family timeline

Privacy boundary:

```text
Admin Alpha Lite and ProductEvent must not show or store child writing text, upgraded sentence text, essay text, AI feedback body, full invite code, real full name, school, address, phone, or photo.
```

## V0.5a Alpha User Foundation

V0.5a adds parent account auth, Magic Code login, legacy parent migration, parent sessions, and auth boundary checks. Keep the V0.4.1b feedback/observation checks above in the rollout; this section extends the same Alpha deployment rather than replacing it.

Required backend env:

| Variable | Railway value |
| --- | --- |
| `AUTH_REQUIRED_FOR_ALPHA` | Start as `false`; switch staging to `true` only for controlled QA. Production must remain `false` until a real production Magic Code email sender/provider integration is shipped and smoke-tested. |
| `AUTH_SECRET_PEPPER` | Strong production secret used for auth token/code hashing. Keep stable across deploys. |
| `AUTH_SESSION_COOKIE_NAME` | `wenlingo_parent_session` unless a production rename is required. |
| `AUTH_SESSION_COOKIE_SECURE` | `true` for Railway HTTPS production and staging. |
| `AUTH_SESSION_COOKIE_SAMESITE` | `lax` when web and API are same-site. Use `none` for Railway Dev smoke when web/API run on separate `*.up.railway.app` hosts, with `AUTH_SESSION_COOKIE_SECURE=true`. |
| `AUTH_SESSION_DAYS` | `30` unless product explicitly changes session length. |
| `AUTH_SESSION_LAST_SEEN_THROTTLE_MINUTES` | `15` unless ops needs a different session write throttle. |
| `AUTH_ALLOWED_ORIGINS` | Staging/production web HTTPS origins allowed for authenticated non-GET requests, comma-separated with no trailing slash. |
| `MAGIC_CODE_TTL_MINUTES` | `10`. |
| `MAGIC_CODE_MAX_ATTEMPTS` | `5`. |
| `MAGIC_CODE_EMAIL_RATE_LIMIT` | `3`. |
| `MAGIC_CODE_IP_RATE_LIMIT` | `20`. |
| `MAGIC_CODE_ALPHA_SESSION_RATE_LIMIT` | `5`. |
| `MAGIC_CODE_FROM_EMAIL` | Reserved for the real production email sender/provider integration. Current V0.5a implementation does not send production email. |
| `MAGIC_CODE_EMAIL_PROVIDER` | Reserved for the real production email sender/provider integration. Current V0.5a implementation returns 503 unless `MAGIC_CODE_DEV_ECHO=true`. |
| `MAGIC_CODE_DEV_ECHO` | `false` in production. `true` is only for local/dev or tightly controlled staging E2E smoke where captured codes are expected. |
| `LEGACY_BIND_WINDOW_DAYS` | `14` unless the migration window is deliberately changed. |

Current build status: `get_email_sender()` returns `DisabledProductionEmailSender` unless `MAGIC_CODE_DEV_ECHO=true`. That means production auth enablement is blocked in this build. Ship and smoke-test a real production email sender/provider integration with `MAGIC_CODE_DEV_ECHO=false` before setting `AUTH_REQUIRED_FOR_ALPHA=true` in production. Staging may use `MAGIC_CODE_DEV_ECHO=true` only for controlled E2E/dev smoke where captured codes are not exposed to real families.

Production must not run with `MAGIC_CODE_DEV_ECHO=true`. The current app does not fail startup automatically when dev echo is enabled; treat `MAGIC_CODE_DEV_ECHO=false` as a manual deployment gate and config audit unless a future startup guard is added. With the current implementation and `MAGIC_CODE_DEV_ECHO=false`, Magic Code requests return 503 because the production email sender is disabled.

Rollout order:

1. Confirm the production database backup/export is available.
2. Run `uv run alembic upgrade head` against the target database to create V0.5a auth tables and columns.
3. Deploy API and web with `AUTH_REQUIRED_FOR_ALPHA=false`; confirm legacy localStorage parent flow still works.
4. Run the smoke tests from this runbook, including invite, child, assessment, sentence, essay, feedback, summary, and admin flows.
5. Enable `AUTH_REQUIRED_FOR_ALPHA=true` in staging and run the V0.5a manual QA checklist in `qa/2026-06-01-v0.5a-alpha-user-foundation-manual-qa.md`. Staging may use `MAGIC_CODE_DEV_ECHO=true` only for controlled E2E/dev smoke; any real-family staging smoke must use the real email sender once it exists.
6. Keep production `AUTH_REQUIRED_FOR_ALPHA=false` until a real production Magic Code email sender/provider integration exists, is configured with `MAGIC_CODE_DEV_ECHO=false`, and passes email delivery smoke.
7. Enable `AUTH_REQUIRED_FOR_ALPHA=true` in production only after that email integration ships, staging manual QA passes, email delivery is confirmed with `MAGIC_CODE_DEV_ECHO=false`, and the security boundary checklist below passes.
8. After the future production auth gate is satisfied and `AUTH_REQUIRED_FOR_ALPHA=true` is deployed, run a production smoke with one invited family and one legacy migration account.

Security boundary rollout gate:

- Expected guarded/pass checks: verify invalid `Origin` or `Referer` and non-JSON authenticated state-changing requests are rejected for routes that currently use the auth state-change guard: `POST /api/alpha/parents`, `POST /api/alpha/legacy-parent-bind`, `POST /api/students/{student_id}/assessment`, `POST /api/students/{student_id}/sentences`, `POST /api/students/{student_id}/readings`, `POST /api/students/{student_id}/reports`, `POST /api/students/{student_id}/feedback-reactions`, `POST /api/students/{student_id}/essays`, and `POST /api/essays/{essay_id}/revision`.
- Known production auth blockers until guarded and verified: `POST /api/auth/logout`, `PATCH /api/auth/account/phone`, `POST /api/alpha/parents/me/children`, `POST /api/alpha/parents/{parent_id}/children`, `POST /api/alpha/parents/me/children/{student_id}/summary-feedback`, and `POST /api/alpha/parents/{parent_id}/children/{student_id}/summary-feedback` mutate authenticated state but do not currently have complete Origin/Referer and JSON-body guard coverage. QA must fail production auth enablement if any of these accept invalid `Origin`/`Referer`; JSON-body routes must also reject non-JSON bodies before production auth is enabled.

Rollback order:

1. Set `AUTH_REQUIRED_FOR_ALPHA=false` and redeploy/restart the API so legacy localStorage parent flow works again.
2. If the app bundle itself is broken, rollback the API and/or web service to the previous working deployment while keeping PostgreSQL intact.
3. Re-run the rollback checklist: legacy parent flow, invite, assessment, sentence, essay, feedback, summary, and admin flow still work.
4. Do not drop auth tables or auth columns after real migration. They may contain verified parent accounts, sessions, and linkage state needed for a later re-enable.
5. Do not delete learning rows while rolling back auth. Protect `ParentUser`, `StudentProfile`, assessments, sentence work, essays, reactions, summaries, feedback, invites, and product events.

Ops scripts:

```bash
cd apps/api

# Existing V0.4.1b invite tooling remains available.
uv run python -m app.ops.create_alpha_invites --count 5 --label-prefix "Alpha Family" --issued-to-note "June 2026 invited family"
uv run python -m app.ops.bind_alpha_invite --parent-id <parent-id> --code <raw-code> --note "Legacy Alpha family"

# V0.5a migration/account tooling.
uv run python -m app.ops.list_unlinked_alpha_parents
uv run python -m app.ops.bind_parent_account --parent-id <parent-id> --email <parent-email>
uv run python -m app.ops.revoke_parent_sessions --email <parent-email>
uv run python -m app.ops.revoke_parent_sessions --account-id <account-id>
```

Use `list_unlinked_alpha_parents` before and after the legacy migration window to find Alpha parents that still need account binding. Use `bind_parent_account` only after verifying the invite label and parent identity with the inviter or support notes. Use `revoke_parent_sessions` when a parent loses access to an email address, reports a suspicious login, or needs all active browser sessions invalidated.

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
First deployment bootstrap command: uv run python -m app.db.init_db && uv run alembic stamp head
Ongoing Pre-deploy Command: uv run alembic upgrade head
Start Command: uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
Public Networking: enabled
```

Keep database initialization and migrations out of the long-running Start Command.

For the first deployment into a brand-new database, temporarily use the bootstrap command as Railway's Pre-deploy Command. `app.db.init_db` creates the current SQLModel schema, and `alembic stamp head` records that schema as the current Alembic revision without replaying historical migrations that may add columns, tables, or constraints already created by `init_db`.

After the first successful deploy, switch Railway's Pre-deploy Command to the ongoing command:

```bash
uv run alembic upgrade head
```

Do not leave the bootstrap command in place for future schema changes. Future migrations must be applied with `alembic upgrade head`; repeatedly stamping head can hide unapplied migrations. The init script must stay idempotent and must not delete, truncate, or reseed Alpha data.

#### First Deployment Recovery

If the first Railway deploy already ran `app.db.init_db` but then attempted `alembic upgrade head`, Alembic may fail on the first migration with a duplicate table, column, or constraint error such as:

```text
psycopg2.errors.DuplicateTable: relation "uq_essay_version_label_per_essay" already exists
```

That means the schema exists, but the `alembic_version` marker was not stamped. Recover by temporarily changing Railway's Pre-deploy Command to:

```bash
uv run alembic stamp head
```

Redeploy the API service once. After it succeeds, change Railway's Pre-deploy Command back to:

```bash
uv run alembic upgrade head
```

Do not drop the PostgreSQL database, do not run downgrade migrations, and do not rerun demo seed scripts to fix this state. The goal is only to align Alembic's version marker with the schema that `init_db` already created.

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
Start Command: corepack pnpm exec next start -H 0.0.0.0 -p $PORT
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
