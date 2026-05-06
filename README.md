# Wenlingo 小文星球

Wenlingo（小文星球）是一个 AI 驱动的中文语文阅读与写作成长平台，面向小学阶段孩子，围绕阅读理解、作文写作、能力诊断与游戏化成长，提供个性化练习、智能反馈和持续进步追踪。

Wenlingo is an AI-powered Chinese literacy platform for children, designed to improve reading comprehension and writing skills through personalized practice, intelligent feedback, and gamified growth journeys.

## Local runtime

Backend dependencies are managed with uv:

```bash
cd apps/api
uv sync --extra dev
uv run pytest
uv run uvicorn app.main:app --reload
```

Frontend dependencies are managed with pnpm:

```bash
cd apps/web
pnpm install
pnpm test
pnpm dev
```

Start local Postgres services from the repository root:

```bash
docker compose up -d
```
