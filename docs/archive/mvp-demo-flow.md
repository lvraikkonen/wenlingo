# MVP Demo Flow Archive

Date: 2026-06-19
Status: Archived in V0.5c.2

## What The MVP Demo Validated

The MVP demo flow validated that a family could enter WenLingo quickly, choose one
of four seeded children, complete a learning loop, and see parent-visible progress.
It was useful for proving the early Draft → AI feedback → Revision → Comparison
→ Encouragement loop before WenLingo had product-grade accounts.

## Original Runtime Shape

- Browser home page called `/api/auth/demo-login`.
- The API seeded `demo@wenlingo.local` with parent id `p1`.
- The API seeded children `s1`, `s2`, `s3`, and `s4`.
- The browser linked directly to child dashboards without requiring a real
  `ParentSession`.

## Why It Was Removed

By V0.5a, WenLingo had `ParentAccount`, `ParentSession`, Magic Code login, and
server-side sessions. By V0.5c.1, same-origin auth, auth failure UX, and
localStorage identity cleanup were stable enough for external Alpha. Keeping an
unauthenticated demo route in production/runtime after that point increased risk
and made login failures harder to diagnose.

## Alpha Replacement

External Alpha users now enter through `/alpha/start`, verify a Magic Code, create
or load a linked family, create children, and use session-aware product APIs.
