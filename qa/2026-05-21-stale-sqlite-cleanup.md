# Stale SQLite Cleanup Runbook

Date: 2026-05-21
Scope: Local manual QA and Playwright E2E only

## Why This Exists

Local SQLite files are ignored by git and can keep old schemas after migrations change. `app.db.init_db` creates missing tables but does not migrate existing SQLite files, so stale files can cause errors such as missing assessment artifact columns.

## Files To Check

- `apps/api/manual-test.db`
- `apps/api/playwright-e2e.db`
- Any local SQLite file referenced by `DATABASE_URL` or `PLAYWRIGHT_DATABASE_URL`

## PowerShell Cleanup

Run from the repository root:

```powershell
if (Test-Path -LiteralPath "apps/api/manual-test.db") {
  Remove-Item -LiteralPath "apps/api/manual-test.db"
}

if (Test-Path -LiteralPath "apps/api/playwright-e2e.db") {
  Remove-Item -LiteralPath "apps/api/playwright-e2e.db"
}
```

## Recreate Tables

```powershell
cd apps/api
$env:DATABASE_URL = "sqlite:///./manual-test.db"
uv run python -m app.db.init_db
```

## Playwright Note

Before `corepack pnpm e2e -- mvp.spec.ts`, remove `apps/api/playwright-e2e.db` so Playwright starts from a schema created from the current SQLModel metadata.
