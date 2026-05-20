# AGENTS.md

## Project

WenLingo / 小文星球 is an AI-assisted Chinese reading and writing learning platform for children.

The product goal is not to generate perfect essays for students. The goal is to help children improve through a positive learning loop:

Draft → AI feedback → Revision → Comparison → Encouragement → Parent-visible progress.

## Primary Development Agent

Codex with Superpowers is the primary implementation agent.

Responsibilities:
- Follow specs and plans.
- Use Superpowers workflows for specs, planning, implementation, testing, and review.
- Implement in small vertical slices.
- Use TDD whenever practical.
- Write or update tests before behavior changes.
- Preserve existing MVP behavior unless the spec explicitly changes it.
- Update relevant documentation after implementation.

## Claude Code / gstack Role

Claude Code with gstack is primarily used for:
- Product review
- UX review
- Architecture review
- QA review
- Release readiness review
- Documentation review

Claude Code / gstack may propose implementation changes, but major behavior changes must be reflected in specs and plans before coding.

## Source of Truth

Use these documents as source of truth, in this order:

1. specs/
2. plans/
3. docs/ai-collaboration-protocol.md
4. tests
5. existing implementation

If implementation conflicts with specs, do not silently change behavior. Report the conflict and update the relevant spec or plan first.

## Current MVP Documents

- specs/2026-05-06-wenlingo-mvp-design.md
- plans/2026-05-06-wenlingo-mvp-implementation.md

## Product Principles

- Encourage before correcting.
- Reward revision, not just completion.
- Feedback must be child-friendly and actionable.
- Parents should see progress, not just scores.
- AI feedback must be structured and traceable.
- Every major learning interaction should create useful data.
- Avoid over-gamification that distracts from real writing improvement.

## Engineering Rules

- Keep changes minimal and scoped.
- Do not rewrite unrelated modules.
- Do not introduce large abstractions without a spec.
- Do not add a new framework without explicit approval.
- Prefer simple data models that support future evaluation and analytics.
- All AI feedback schemas must be versioned.
- All prompt changes must be traceable.
- Database migrations must include tests or verification steps.

## Testing Rules

Before completing a task:
- Run relevant unit tests.
- Run relevant integration tests.
- Add tests for new behavior.
- Summarize what was tested and what was not tested.

### Windows / Codex Verification Notes

- In this environment, `pnpm` may not be available on `PATH`. If `pnpm ...`
  is not recognized, use `corepack pnpm ...` for web commands. Do not treat
  `pnpm` command resolution as a test failure.
- Before running Playwright E2E, remove the ignored local SQLite database
  `apps/api/playwright-e2e.db` if it exists. The Playwright API startup uses
  `app.db.init_db`, which creates missing tables but does not migrate existing
  SQLite tables. A stale database can retain an old schema and cause errors
  such as missing columns on `llmcalllog`.

## Documentation Rules

When behavior changes:
- Update the relevant spec or plan.
- Add implementation notes if needed.
- Keep docs concise and dated.

### Artifact Locations

Superpowers-generated collaboration artifacts should be stored in the project-root folders, not under plugin or temporary workflow directories:

- Brainstorming/design specs: `specs/`
- Implementation plans: `plans/`
- QA reports, release checks, and manual validation results: `qa/`

If a Superpowers skill suggests a default path such as `docs/superpowers/specs/`, use the project-root folder above instead.

## Do Not Do

- Do not generate final essay content for children as the main value.
- Do not optimize for scores only.
- Do not shame or discourage the child.
- Do not add complex gamification before the learning loop is stable.
- Do not make product direction changes during implementation without updating specs.
