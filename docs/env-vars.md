# Environment Variables

This document is the canonical checklist for WenLingo local, Railway Dev,
staging, and production configuration. Keep secrets server-side. Never expose
API keys, database URLs, Admin tokens, or auth peppers through `NEXT_PUBLIC_*`.

## API Service

Set these on `wenlingo-api` unless noted otherwise.

### Base Runtime

| Variable | Default | Required | Secret | Redeploy needed | Notes |
| --- | --- | --- | --- | --- | --- |
| `ENVIRONMENT` | `development` | Yes | No | API restart | Use `development`, `staging`, or `production`. Dev Echo is allowed only in `development`. |
| `DATABASE_URL` | Local PostgreSQL URL | Yes | Yes | API restart | Use the Railway PostgreSQL `DATABASE_URL` in deployed environments. |
| `TEST_DATABASE_URL` | Local test PostgreSQL URL | Local tests | Yes | No | Used by tests and local verification. |
| `API_BASE_URL` | `http://localhost:8000` | Optional | No | API restart | API public origin for internal references. |
| `CORS_ALLOW_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Yes | No | API redeploy/restart | Comma-separated web origins, no trailing slash. |
| `ALPHA_ADMIN_TOKEN` | empty | Deployed Admin | Yes | API restart | Required for `/admin/alpha` API access. |

### Auth And Sessions

| Variable | Default | Required | Secret | Redeploy needed | Notes |
| --- | --- | --- | --- | --- | --- |
| `AUTH_REQUIRED_FOR_ALPHA` | `false` | Yes | No | API restart | Set `true` when Alpha routes require Magic Code sessions. |
| `AUTH_SECRET_PEPPER` | empty | Yes when auth is enabled | Yes | API restart | Stable secret for session and Magic Code hashing. Rotating invalidates old codes/sessions. |
| `AUTH_SESSION_COOKIE_NAME` | `wenlingo_parent_session` | Optional | No | API restart | Keep stable unless intentionally renaming cookies. |
| `AUTH_SESSION_COOKIE_SECURE` | `true` | Deployed HTTPS | No | API restart | Use `true` on Railway HTTPS. |
| `AUTH_SESSION_COOKIE_SAMESITE` | `lax` | Yes | No | API restart | Use `lax` for same-origin Alpha proxy. Use `none` only for controlled direct cross-site API testing, with secure cookies. |
| `AUTH_SESSION_DAYS` | `30` | Optional | No | API restart | Parent login session duration. |
| `AUTH_SESSION_LAST_SEEN_THROTTLE_MINUTES` | `15` | Optional | No | API restart | Reduces session write frequency. |
| `AUTH_ALLOWED_ORIGINS` | empty | Required for auth state changes | No | API restart | Comma-separated allowed web origins for authenticated non-GET requests. |

Use `AUTH_SESSION_COOKIE_SAMESITE=lax`, `AUTH_SESSION_COOKIE_SECURE=true`,
`Path=/`, and no cookie domain for same-origin Alpha proxy. Use
`SameSite=none` only for controlled direct cross-site API testing.

### Demo Runtime

V0.5c.2 removed the production/runtime MVP demo login route. There is no
`DEMO_MODE_ENABLED` production escape hatch. Demo-like seed data may exist only in
dev/test/archive contexts and must not be imported by production API route
modules.

### Magic Code

| Variable | Default | Required | Secret | Redeploy needed | Notes |
| --- | --- | --- | --- | --- | --- |
| `MAGIC_CODE_TTL_MINUTES` | `10` | Optional | No | API restart | Code expiry window. |
| `MAGIC_CODE_MAX_ATTEMPTS` | `5` | Optional | No | API restart | Verification attempts per code. |
| `MAGIC_CODE_EMAIL_RATE_LIMIT` | `3` | Optional | No | API restart | Per-email request limit. |
| `MAGIC_CODE_IP_RATE_LIMIT` | `20` | Optional | No | API restart | Per-IP request limit. |
| `MAGIC_CODE_ALPHA_SESSION_RATE_LIMIT` | `5` | Optional | No | API restart | Per Alpha browser-session request limit. |
| `MAGIC_CODE_DEV_ECHO` | `false` | Yes | No | API restart | `true` only for internal QA in `ENVIRONMENT=development`. Startup fails in staging/production when enabled. |

### Email Delivery

| Variable | Default | Required | Secret | Redeploy needed | Notes |
| --- | --- | --- | --- | --- | --- |
| `MAGIC_CODE_EMAIL_PROVIDER` | empty | Yes for real email | No | API restart | Use `resend` or `smtp`. Empty disables real delivery unless Dev Echo is enabled. |
| `MAGIC_CODE_FROM_EMAIL` | empty | Yes for real email | No | API restart | Must be verified by the chosen provider. |
| `RESEND_API_KEY` | empty | Yes when provider is `resend` | Yes | API restart | Store only on the API service. |
| `RESEND_TIMEOUT_SECONDS` | `10` | Optional | No | API restart | Resend request timeout. |
| `SMTP_HOST` | empty | Yes when provider is `smtp` | No | API restart | SMTP server host. |
| `SMTP_PORT` | `465` | Yes when provider is `smtp` | No | API restart | SMTP port. |
| `SMTP_USERNAME` | empty | Yes when provider is `smtp` | Yes | API restart | SMTP login. |
| `SMTP_PASSWORD` | empty | Yes when provider is `smtp` | Yes | API restart | Use an app authorization code, not an account password. |
| `SMTP_USE_SSL` | `true` | Optional | No | API restart | Use implicit TLS. |
| `SMTP_USE_STARTTLS` | `false` | Optional | No | API restart | Use STARTTLS when required by provider. |
| `SMTP_TIMEOUT_SECONDS` | `10` | Optional | No | API restart | SMTP timeout. |

### LLM And Limits

| Variable | Default | Required | Secret | Redeploy needed | Notes |
| --- | --- | --- | --- | --- | --- |
| `LLM_PROVIDER` | `mock` | Yes | No | API restart | Use `http` for real LLM calls. |
| `LLM_API_KEY` | empty | Yes when `LLM_PROVIDER=http` | Yes | API restart | Server-side only. |
| `LLM_MODEL` | empty | Yes when `LLM_PROVIDER=http` | No | API restart | Provider model name. |
| `LLM_BASE_URL` | empty | Yes when `LLM_PROVIDER=http` | No | API restart | Chat completions-compatible base URL, no trailing slash preferred. |
| `LLM_PROMPT_VERSION` | empty | Optional | No | API restart | Optional explicit override for prompt-version logging/testing only; leave unset so task wrappers use Prompt Registry versions. |
| `LLM_DAILY_LIMIT_ENABLED` | `false` | Yes for limit QA | No | API restart | Must be `true` for Daily limit checks to trigger. |
| `LLM_DAILY_LIMIT_PER_STUDENT_TASK` | `5` | Optional | No | API restart | Generic per-student task limit for older tasks. |
| `SENTENCE_CHALLENGE_DAILY_LIMIT_PER_STUDENT` | `10` | V0.5b sentence QA | No | API restart | Generation limit for sentence challenges. |
| `SENTENCE_FEEDBACK_DAILY_LIMIT_PER_STUDENT` | `10` | V0.5b sentence QA | No | API restart | Feedback limit for generated/free-input sentence work. |
| `LLM_DAILY_LIMIT_TIMEZONE` | `Asia/Shanghai` | Yes | No | API restart | Product-day boundary for limit counting and Admin usage dates. |
| `LLM_INPUT_COST_PER_1K_TOKENS` | `0.0` | Dev fallback only | No | API restart | Generic cost estimate input rate. Used only as a development fallback for routed HTTP models that are not in the Cost Registry and do not have profile-specific pricing. Do not rely on this for staging/production routed model overrides. |
| `LLM_OUTPUT_COST_PER_1K_TOKENS` | `0.0` | Dev fallback only | No | API restart | Generic cost estimate output rate. Used only as a development fallback for routed HTTP models that are not in the Cost Registry and do not have profile-specific pricing. Do not rely on this for staging/production routed model overrides. |
| `LLM_PRIMARY_INPUT_COST_PER_1K_TOKENS` | `0.0` | HTTP primary override pricing | No | API restart | Input cost for `LLM_PRIMARY_HTTP_MODEL` when the routed primary override is not in the Cost Registry. |
| `LLM_PRIMARY_OUTPUT_COST_PER_1K_TOKENS` | `0.0` | HTTP primary override pricing | No | API restart | Output cost for `LLM_PRIMARY_HTTP_MODEL` when the routed primary override is not in the Cost Registry. |
| `LLM_FALLBACK_INPUT_COST_PER_1K_TOKENS` | `0.0` | HTTP fallback override pricing | No | API restart | Input cost for `LLM_FALLBACK_HTTP_MODEL` when the routed fallback override is not in the Cost Registry. |
| `LLM_FALLBACK_OUTPUT_COST_PER_1K_TOKENS` | `0.0` | HTTP fallback override pricing | No | API restart | Output cost for `LLM_FALLBACK_HTTP_MODEL` when the routed fallback override is not in the Cost Registry. |

## V0.5c AI Routing

V0.5c routes AI tasks through code-level task and model registries. Environment variables provide credentials and deployment-specific model overrides only.

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | yes | `mock` for local tests, `http` for OpenAI-compatible HTTP profiles. |
| `LLM_PRIMARY_HTTP_BASE_URL` | staging/production real provider | Base URL for the primary OpenAI-compatible provider profile. |
| `LLM_PRIMARY_HTTP_API_KEY` | staging/production real provider | API key for the primary profile. |
| `LLM_PRIMARY_HTTP_MODEL` | optional | Concrete model override for the primary logical model. Must have Cost Registry pricing or `LLM_PRIMARY_*_COST_PER_1K_TOKENS` pricing in staging/production. |
| `LLM_FALLBACK_HTTP_BASE_URL` | staging/production real provider | Base URL for the fallback OpenAI-compatible provider profile. |
| `LLM_FALLBACK_HTTP_API_KEY` | staging/production real provider | API key for the fallback profile. |
| `LLM_FALLBACK_HTTP_MODEL` | optional | Concrete model override for the fallback logical model. Must have Cost Registry pricing or `LLM_FALLBACK_*_COST_PER_1K_TOKENS` pricing in staging/production. |
| `LLM_DAILY_LIMIT_ENABLED` | recommended in Dev/Alpha | Enables task-level daily limits. |
| `LLM_DAILY_LIMIT_TIMEZONE` | yes | Product day timezone, default `Asia/Shanghai`. |

Do not use global `LLM_MODEL` as a production AI routing bypass after V0.5c. All enabled production AI tasks must resolve through ModelRouter. When primary and fallback providers use different deployed model overrides, configure their prices separately with the profile-specific cost variables above; the generic `LLM_INPUT_COST_PER_1K_TOKENS` / `LLM_OUTPUT_COST_PER_1K_TOKENS` pair is only a development fallback.

### Legacy Migration

| Variable | Default | Required | Secret | Redeploy needed | Notes |
| --- | --- | --- | --- | --- | --- |
| `LEGACY_BIND_WINDOW_DAYS` | `14` | Optional | No | API restart | Window for binding legacy localStorage families to Magic Code accounts. |

## Web Service

Set these on `wenlingo-web`. Server-side web runtime variables such as
`API_PROXY_TARGET` are read by Next.js rewrites on the web service and require a
restart/redeploy when changed. Next.js embeds `NEXT_PUBLIC_*` values into the
browser bundle, so those changes require rebuilding/redeploying the web service.

| Variable | Default | Required | Secret | Redeploy needed | Notes |
| --- | --- | --- | --- | --- | --- |
| `API_PROXY_TARGET` | unset locally | Railway Web service | No | Web restart/redeploy | Server-side API origin used by Next.js rewrites for same-origin `/api/*` browser traffic. External Alpha should set this to the API service origin and leave `NEXT_PUBLIC_API_BASE_URL` empty or `/api`. |
| `NEXT_PUBLIC_API_BASE_URL` | empty | Optional | No | Web rebuild/redeploy | Browser API base override. External Alpha should leave this empty or set `/api` so calls remain same-origin. Use an absolute API URL only for controlled direct-API testing. |

## Verification And E2E

| Variable | Default | Required | Secret | Redeploy needed | Notes |
| --- | --- | --- | --- | --- | --- |
| `PLAYWRIGHT_DATABASE_URL` | `sqlite:///./playwright-e2e.db` | Optional | Maybe | No | Used by web Playwright setup to point E2E at a disposable database. |
| `PORT` | Provided by Railway | Deployed services | No | Service restart | Railway injects this. Start commands must bind `0.0.0.0:$PORT`. |

## Railway Dev Checklist

For the current Railway Dev Alpha environment, verify at minimum:

```text
ENVIRONMENT=development
DATABASE_URL=<Railway PostgreSQL reference>
CORS_ALLOW_ORIGINS=<web public HTTPS origin, no trailing slash>
AUTH_REQUIRED_FOR_ALPHA=true
AUTH_SECRET_PEPPER=<stable secret>
AUTH_ALLOWED_ORIGINS=<web public HTTPS origin, no trailing slash>
MAGIC_CODE_EMAIL_PROVIDER=resend
MAGIC_CODE_FROM_EMAIL=<verified sender>
RESEND_API_KEY=<server-side secret>
MAGIC_CODE_DEV_ECHO=false
LLM_PROVIDER=http
# Legacy non-routed compatibility only; not sufficient for V0.5c routed tasks.
LLM_API_KEY=<server-side secret>
LLM_MODEL=<model>
LLM_BASE_URL=<provider base URL>
# V0.5c routed AI provider profiles.
LLM_PRIMARY_HTTP_BASE_URL=<primary provider base URL>
LLM_PRIMARY_HTTP_API_KEY=<server-side secret>
LLM_PRIMARY_HTTP_MODEL=<primary routed model>
LLM_FALLBACK_HTTP_BASE_URL=<fallback provider base URL>
LLM_FALLBACK_HTTP_API_KEY=<server-side secret>
LLM_FALLBACK_HTTP_MODEL=<fallback routed model>
# Dev-only same-price fallback is acceptable when primary/fallback use the same model.
LLM_INPUT_COST_PER_1K_TOKENS=<dev generic input cost>
LLM_OUTPUT_COST_PER_1K_TOKENS=<dev generic output cost>
# For staging/production model overrides, configure profile-specific pricing instead.
LLM_PRIMARY_INPUT_COST_PER_1K_TOKENS=<primary input cost>
LLM_PRIMARY_OUTPUT_COST_PER_1K_TOKENS=<primary output cost>
LLM_FALLBACK_INPUT_COST_PER_1K_TOKENS=<fallback input cost>
LLM_FALLBACK_OUTPUT_COST_PER_1K_TOKENS=<fallback output cost>
LLM_DAILY_LIMIT_ENABLED=true
SENTENCE_CHALLENGE_DAILY_LIMIT_PER_STUDENT=10
SENTENCE_FEEDBACK_DAILY_LIMIT_PER_STUDENT=10
LLM_DAILY_LIMIT_TIMEZONE=Asia/Shanghai
API_PROXY_TARGET=<API public HTTPS origin, no trailing slash>
NEXT_PUBLIC_API_BASE_URL=
```

After changing `CORS_ALLOW_ORIGINS`, `AUTH_ALLOWED_ORIGINS`, email, auth, LLM,
or limit variables, redeploy/restart `wenlingo-api`. After changing
`API_PROXY_TARGET` or `NEXT_PUBLIC_API_BASE_URL`, restart/redeploy or
rebuild/redeploy `wenlingo-web` as applicable.

### Daily Limit Smoke Trigger

For V0.5b.1 Dev smoke, temporarily lower one sentence limit for the masked QA
student/environment so the limit can be verified without ten real LLM calls:

```text
LLM_DAILY_LIMIT_ENABLED=true
SENTENCE_CHALLENGE_DAILY_LIMIT_PER_STUDENT=1
# or
SENTENCE_FEEDBACK_DAILY_LIMIT_PER_STUDENT=1
```

After verifying the child rest message and Admin `Limits` count, restore normal
Alpha values:

```text
SENTENCE_CHALLENGE_DAILY_LIMIT_PER_STUDENT=10
SENTENCE_FEEDBACK_DAILY_LIMIT_PER_STUDENT=10
```

Record the temporary values, restore time, and final values in the release QA
checklist.
