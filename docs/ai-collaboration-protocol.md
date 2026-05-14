# WenLingo AI Collaboration Protocol

## Agent Split

Claude Code + gstack:
- Thinks, reviews, validates, and releases.

Codex + Superpowers:
- Plans, implements, tests, and refactors.

## Golden Rule

Only one agent drives implementation at a time.

Claude Code may review implementation.
Codex may propose product changes.
But neither agent should silently change the other agent’s source-of-truth documents.

## Workflow

1. Claude Code + gstack reviews product direction.
2. Claude Code + gstack produces or updates specs.
3. Codex + Superpowers creates implementation plan.
4. Codex + Superpowers implements one vertical slice.
5. Codex summarizes changes and test results.
6. Claude Code + gstack reviews UX, architecture, QA, and release readiness.
7. Codex fixes review findings.
8. Docs are updated.

## Required Handoff: Claude/gstack to Codex

- Goal
- Source documents
- Acceptance criteria
- Constraints
- Do-not-do list
- Test expectations

## Required Handoff: Codex to Claude/gstack

- Implemented changes
- Files changed
- Tests added
- Tests run
- Known issues
- Review requested

## Conflict Resolution

If specs, plans, tests, and implementation conflict:

1. Do not guess.
2. Document the conflict.
3. Prefer specs for product behavior.
4. Prefer tests for current verified behavior.
5. Update specs/plans/tests before major code changes.

## WenLingo Product North Star

Help children improve Chinese reading and writing through repeated, encouraging, measurable practice.

The product should make children feel:
- I can improve.
- I know what to change.
- I am not afraid of writing.
- My effort is visible.

The product should help parents see:
- What the child practiced.
- What improved.
- What still needs help.
- What to do next.