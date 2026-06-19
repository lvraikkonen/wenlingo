# WenLingo Smoke Checklist Template

Date:
Tester:
Environment:
Web URL:
API URL:
Commit:

## Environment

- [ ] Web and API deploys point at the intended commit.
- [ ] `API_PROXY_TARGET` is set for external Alpha.
- [ ] Browser API calls use Web origin `/api/*`.
- [ ] `AUTH_SESSION_COOKIE_SECURE=true`.
- [ ] `AUTH_SESSION_COOKIE_SAMESITE=lax` for same-origin Alpha.
- [ ] `MAGIC_CODE_DEV_ECHO` setting matches test intent.
- [ ] Daily-limit env values match test intent.

## Login

- [ ] Chrome normal Magic Code login.
- [ ] Chrome Incognito Magic Code login.
- [ ] Safari or mobile browser Magic Code login.
- [ ] Refresh `/parent/children` after login and remain authenticated.
- [ ] Invalid Magic Code shows code-specific error.
- [ ] Missing session shows session-specific message.

## Core Learning Flow

- [ ] Parent children page opens.
- [ ] Child Dashboard opens.
- [ ] Sentence challenge generation works.
- [ ] Sentence feedback works.
- [ ] Parent summary/report opens.
- [ ] Core pages provide in-app navigation without browser Back/Forward.

## AI Reliability

- [ ] Primary success is logged.
- [ ] Fallback success is logged.
- [ ] Daily-limit hit returns child-friendly rest message.
- [ ] Daily-limit hit creates no provider call.
- [ ] Admin AI usage shows limit hits and fallback status.

## Privacy

- [ ] Admin pages do not show raw child writing.
- [ ] Admin pages do not show raw prompts or raw LLM responses.
- [ ] Admin pages do not show raw Magic Codes, invite codes, API keys, full emails, or full phone numbers.

## Go / No-Go

- [ ] Go
- [ ] No-Go

Notes:
