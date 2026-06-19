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
| `AUTH_SESSION_COOKIE_SAMESITE` | `lax` when web and API are same-origin or same-site. Historical Railway Dev direct web-to-API smoke on separate `*.up.railway.app` hosts used `none` with `AUTH_SESSION_COOKIE_SECURE=true`; keep that only as a controlled direct cross-site API fallback test, not the external Alpha recommendation. |
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

## V0.5a.1 Alpha Dev Hardening

V0.5a.1 hardens Railway Dev auth/admin operations for low-volume Alpha smoke. Railway Dev may use QQ Mail SMTP for low-volume Magic Code delivery with `MAGIC_CODE_DEV_ECHO=false`. Use a QQ Mail authorization code for SMTP auth; do not use the QQ account password.

Required backend env:

| Variable | Railway Dev value |
| --- | --- |
| `MAGIC_CODE_DEV_ECHO` | `false` |
| `MAGIC_CODE_EMAIL_PROVIDER` | `smtp` |
| `MAGIC_CODE_FROM_EMAIL` | `<your@qq.com>` |
| `SMTP_HOST` | `smtp.qq.com` |
| `SMTP_PORT` | `465` |
| `SMTP_USERNAME` | `<your@qq.com>` |
| `SMTP_PASSWORD` | QQ Mail authorization code, not account password |
| `SMTP_USE_SSL` | `true` |
| `SMTP_USE_STARTTLS` | `false` |
| `SMTP_TIMEOUT_SECONDS` | `10` |

Smoke checklist:

1. Request Magic Code with `MAGIC_CODE_DEV_ECHO=false`.
2. Confirm QQ inbox arrival.
3. Generate one invite from `/admin/alpha`.
4. Create family with generated invite.
5. Disable account and confirm active sessions lose access.
6. Re-enable and confirm Magic Code login works.
7. Revoke unused invite and confirm it cannot validate.
8. Confirm consumed invites cannot be revoked.
9. Open parent report page and confirm no server error page appears.

As part of the Railway Dev rollout, run the full QA checklist in `qa/2026-06-04-v0.5a.1-alpha-dev-hardening-manual-qa.md` after the smoke checklist.

## V0.5a.2 Alpha QA Closure Hardening

V0.5a.2 treats real SMTP delivery on Railway Dev as a known blocked/skipped
check. Railway Dev QA uses Magic Code Dev Echo until a later email-provider
release changes that decision.

Required Railway Dev auth env:

| Variable | Railway Dev value |
| --- | --- |
| `MAGIC_CODE_DEV_ECHO` | `true` |

Operator rules:

1. Set `MAGIC_CODE_DEV_ECHO=true` on `wenlingo-api`, not `wenlingo-web`.
2. Confirm the variable is set in the Railway environment serving the current
   Dev web URL.
3. Redeploy or restart `wenlingo-api` after changing the variable.
4. Use Magic Code `123456` for controlled Dev QA.
5. If `/alpha/start` still waits for the SMTP timeout, re-check service,
   environment, and API redeploy state before debugging frontend code.

Admin Alpha includes a permanent test-account hard delete action for Dev/QA
cleanup. It is guarded by a test-email allowlist and the confirmation text
`DELETE TEST ACCOUNTS`. Do not use it for real Alpha families. The action must
reject protected demo/system accounts and any batch containing a non-test email.

## V0.5b AI Infrastructure And Sentence Train

Magic Code email config:

| Variable | V0.5b Railway Dev value |
| --- | --- |
| `ENVIRONMENT` | `development` for Railway Dev, `staging` for staging, `production` for production |
| `MAGIC_CODE_EMAIL_PROVIDER` | `resend` |
| `MAGIC_CODE_FROM_EMAIL` | `login@your-verified-domain.example` |
| `RESEND_API_KEY` | Resend API key stored as a server-side secret |
| `RESEND_TIMEOUT_SECONDS` | `10` |
| `MAGIC_CODE_DEV_ECHO` | `true` only for internal QA in `ENVIRONMENT=development`; `false` in staging and production |

`MAGIC_CODE_DEV_ECHO=true` is not real email delivery. It is only for internal QA in `ENVIRONMENT=development`, where the dev code is intentionally echoed for testers. Startup must fail fast when `ENVIRONMENT=staging` or `ENVIRONMENT=production` and `MAGIC_CODE_DEV_ECHO=true`; do not use database URL heuristics for this guard.

External Alpha invitations are blocked until the Resend sending domain is verified and at least one real Magic Code email is delivered successfully from `MAGIC_CODE_FROM_EMAIL`. If the domain is pending, Railway Dev may continue using Dev Echo for internal QA only, but the build is not ready for external family invitations.

AI usage settings:

| Variable | Default |
| --- | --- |
| `LLM_PROVIDER` | `http` for real provider calls |
| `LLM_PRIMARY_HTTP_BASE_URL` | Primary provider base URL |
| `LLM_PRIMARY_HTTP_API_KEY` | Primary provider server-side secret |
| `LLM_PRIMARY_HTTP_MODEL` | Primary routed model with Cost Registry pricing |
| `LLM_FALLBACK_HTTP_BASE_URL` | Fallback provider base URL |
| `LLM_FALLBACK_HTTP_API_KEY` | Fallback provider server-side secret |
| `LLM_FALLBACK_HTTP_MODEL` | Fallback routed model with Cost Registry pricing |
| `SENTENCE_CHALLENGE_DAILY_LIMIT_PER_STUDENT` | `10` |
| `SENTENCE_FEEDBACK_DAILY_LIMIT_PER_STUDENT` | `10` |
| `LLM_DAILY_LIMIT_TIMEZONE` | `Asia/Shanghai` |
| `LLM_INPUT_COST_PER_1K_TOKENS` | `0` |
| `LLM_OUTPUT_COST_PER_1K_TOKENS` | `0` |

Legacy non-routed `LLM_API_KEY`, `LLM_MODEL`, and `LLM_BASE_URL` may still be needed for older compatibility paths, but they are not sufficient for V0.5c routed tasks.

### V0.5c AI Routing Smoke

Before inviting or expanding Alpha families on a V0.5c deploy:

- Confirm startup passes AI routing validation.
- Confirm each enabled task resolves a primary and fallback logical model.
- Confirm staging/production routed models have Cost Registry pricing.
- Run one sentence challenge primary-success smoke.
- Run one controlled fallback-success smoke.
- Run one deterministic local fallback smoke.
- Run one daily-limit smoke and confirm no provider call is made after the limit.
- Open Admin `AI 使用量` / AI usage and confirm final status, fallback counts, pricing status, token totals, and average latency appear without raw child text or raw provider responses.

Rollback rule: roll back the deployment or pin the previous known-good commit. Do not route around ModelRouter with global `LLM_MODEL`.

### Same-Origin API Proxy For External Alpha

External Alpha browser traffic should call the Web origin only:

```text
Browser -> wenlingo-web /api/* -> API service /api/*
```

Railway Web env:

- `API_PROXY_TARGET=https://<wenlingo-api-service-origin>`
- `NEXT_PUBLIC_API_BASE_URL=` or `NEXT_PUBLIC_API_BASE_URL=/api`

Railway API env:

- `AUTH_SESSION_COOKIE_SECURE=true`
- `AUTH_SESSION_COOKIE_SAMESITE=lax`
- `CORS_ALLOW_ORIGINS=https://<wenlingo-web-origin>`
- `AUTH_ALLOWED_ORIGINS=https://<wenlingo-web-origin>`

Do not send external Alpha families a direct API origin. Direct cross-site API testing is an internal fallback only.

### V0.5c.2 Session Cleanup

V0.5c.2 removes `/api/auth/demo-login` from production/runtime. External Alpha
must use Magic Code login and `ParentSession`.

Recommended Alpha cleanup command:

```bash
cd apps/api
uv run python -m app.ops.cleanup_parent_sessions --dry-run --revoked-retention-days 30 --expired-retention-days 30
uv run python -m app.ops.cleanup_parent_sessions --execute --revoked-retention-days 30 --expired-retention-days 30
```

Run dry-run first and confirm the summary. The command does not print raw session
tokens or token hashes. Do not use 0-day retention for Alpha; keep 30 days so
recent support investigations can still reason about expired or revoked sessions.

### V0.5b AI Sentence Challenge Smoke

1. Dev Echo login with code `123456` in `ENVIRONMENT=development`.
2. Configure Resend in Railway Dev and verify one real Magic Code email after domain verification.
3. Confirm staging/production startup fails if Dev Echo is enabled.
4. Create or use an Alpha family.
5. Open sentence workshop and receive an AI-generated or fallback challenge.
6. Complete one challenge and verify short feedback, XP, and reaction.
7. Challenge again and verify a new generated row.
8. Exercise the daily limit path and verify `今天的句子挑战已经完成很多啦，休息一下，明天继续闯关！`.
9. Switch to `自己带句子来练` and verify the old flow still works.
10. Open parent summary and verify sentence training is lightly reflected.
11. Open Admin `AI 使用量` and verify aggregate LLM usage and daily limit hits appear.
12. Revoke an unused invite and verify it is hidden by default but visible when toggled.
13. Verify cross-family sentence challenge access is rejected.

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
| `LLM_PRIMARY_HTTP_BASE_URL` | Primary provider base URL for V0.5c routed tasks. |
| `LLM_PRIMARY_HTTP_API_KEY` | Primary provider server-side secret. |
| `LLM_PRIMARY_HTTP_MODEL` | Primary routed model with Cost Registry pricing. |
| `LLM_FALLBACK_HTTP_BASE_URL` | Fallback provider base URL for V0.5c routed tasks. |
| `LLM_FALLBACK_HTTP_API_KEY` | Fallback provider server-side secret. |
| `LLM_FALLBACK_HTTP_MODEL` | Fallback routed model with Cost Registry pricing. |
| `LLM_API_KEY` | Legacy non-routed compatibility key; not sufficient for V0.5c routed tasks. |
| `LLM_MODEL` | Legacy non-routed compatibility model; do not use as a ModelRouter bypass. |
| `LLM_BASE_URL` | Legacy non-routed compatibility base URL. |
| `LLM_PROMPT_VERSION` | empty/unset; optional explicit override for prompt-version logging/testing only. Leave unset so task wrappers use Prompt Registry versions. |

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
| `API_PROXY_TARGET` | The generated public HTTPS origin for `wenlingo-api` after Public Networking is enabled, with no trailing slash. |
| `NEXT_PUBLIC_API_BASE_URL` | Empty or `/api` for external Alpha. Use an absolute API URL only for controlled direct-API testing. |

Set `API_PROXY_TARGET` on `wenlingo-web` so Next.js rewrites same-origin
browser calls from `/api/*` to the API service. Keep `NEXT_PUBLIC_API_BASE_URL`
empty or `/api` for external Alpha so the browser stays on the Web origin.

On first deployment, set `CORS_ALLOW_ORIGINS` and `AUTH_ALLOWED_ORIGINS` after
the web public domain exists, then redeploy `wenlingo-api`. Set
`API_PROXY_TARGET` before starting `wenlingo-web`. If `API_PROXY_TARGET`,
`NEXT_PUBLIC_API_BASE_URL`, `CORS_ALLOW_ORIGINS`, or `AUTH_ALLOWED_ORIGINS`
changes later, manually redeploy the affected service so runtime rewrites, the
browser bundle, CORS, and auth origin checks use the new values.

Use a full HTTPS origin for `API_PROXY_TARGET`, for example:

```text
https://wenlingo-api-production.up.railway.app
```

Do not include a trailing slash or path. Do not send this direct API origin to
external Alpha families.

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
