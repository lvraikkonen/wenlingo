# WenLingo Family Test Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the demo family experience complete enough for a normal family tester to enter, switch among four child profiles, finish the essay and sentence paths, see useful settlement/report evidence, and avoid broken unfinished-module routes.

**Architecture:** Keep the existing V0.2 essay quality spine as the backbone and extend it rather than replacing it. Backend work adds student-level LLM traceability, real-provider daily usage protection, and sentence feedback through the shared validated LLM runner. Frontend work adds a lightweight family shell, connected navigation, child-friendly sentence polish, construction states, and E2E coverage that uses visible links instead of manual URL jumps.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy, Alembic, Pydantic, pytest, Next.js App Router, React 19, TypeScript, Tailwind CSS 4, Vitest, React Testing Library, Playwright.

---

## Source Documents

- Approved design spec: `specs/2026-05-15-wenlingo-family-test-readiness-design.md`
- V0.2 quality spine spec: `specs/2026-05-14-wenlingo-v0.2-quality-spine-design.md`
- V0.2 quality spine plan: `plans/2026-05-14-wenlingo-v0.2-quality-spine-implementation.md`
- gstack review: `specs/2026-05-15-wenlingo-mvp-gstack-review.md`
- AI quality review: `qa/2026-05-14-v0.2-ai-quality-review.md`
- Local agent rules: `AGENT.md`, `CLAUDE.md`

## Execution Rules

- Run tasks sequentially and stop for review after every task.
- Use TDD for every behavior change.
- Keep commits task-sized. Commit only after the task verification command passes.
- Preserve the existing V0.2 essay behavior unless this plan explicitly changes it.
- Do not add accounts, authentication, invitations, permissions, full analytics, token/cost accounting, new learning modules, or complex gamification.
- Keep child-facing errors warm and non-technical.
- Preserve readable UTF-8 Chinese in code, tests, UI labels, and docs.
- Do not stage `.env`.

## File Structure Map

- Modify: `apps/api/app/domain/models.py` - add nullable `LLMCallLog.student_id` and stored `task_name` for per-student per-task usage protection.
- Create: `apps/api/app/db/migrations/versions/20260515_family_test_llm_student_usage.py` - migrate `llmcalllog.student_id` and `llmcalllog.task_name`.
- Modify: `apps/api/app/core/config.py` and `.env-sample` - add disabled-by-default daily LLM limit settings.
- Modify: `apps/api/app/services/ai_tasks.py` - pass `student_id`, store `task_name`, enforce daily real-provider limit, add sentence fallback, and run sentence feedback through `run_validated_llm_task`.
- Modify: `apps/api/app/api/routes/essays.py` - pass student context and usage settings to essay LLM tasks, record completed task count in settlement evidence.
- Modify: `apps/api/app/api/routes/sentences.py` - replace direct `MockLLMProvider()` construction with provider DI, shared validation, fallback, logging, and usage settings.
- Modify: `apps/api/app/services/llm_provider.py` - tighten `essay_feedback` provider contract toward exactly one revision task while allowing schema fallback to protect the UI.
- Modify: `apps/api/app/services/recommendations.py` and `apps/api/app/services/reports.py` - make four demo profiles visibly differ in recommendations and report weak points.
- Modify: backend tests under `apps/api/tests/` - cover model/migration fields, logging context, sentence DI/resilience/fallback, daily limits, profile differentiation, report weak points, and essay settlement evidence.
- Create: `apps/web/src/components/FamilyTopbar.tsx` - lightweight app shell with product identity, current child display, child switcher, and primary navigation.
- Create: `apps/web/src/components/ConstructionState.tsx` - shared friendly construction state for planned-but-unfinished modules.
- Modify: web route pages under `apps/web/src/app/children/[studentId]/` and `apps/web/src/app/parent/[studentId]/report/page.tsx` - render shell/navigation, default essay tasks selected, polish sentence page, show construction state for Reading Canyon, and add clear dashboard/report actions.
- Modify: `apps/web/src/components/TaskCards.tsx`, `PlanetMap.tsx`, `SettlementPanel.tsx` - connect task/map links, remove duplicate labels, and render completed revision task count.
- Modify: `apps/web/src/lib/api.ts` and `apps/web/src/lib/types.ts` - expand sentence feedback and settlement types.
- Modify: web tests under `apps/web/tests/` and `apps/web/e2e/mvp.spec.ts` - cover shell, switcher, task entry, sentence polish, construction state, parent navigation, and no-manual-URL E2E.
- Create: `qa/2026-05-15-family-test-readiness-manual-qa.md` after manual QA - record four-profile checks and real LLM checks for 小宇 essay and sentence flows.

---

### Task 1: Add Student LLM Traceability And Daily Usage Protection

**Files:**
- Modify: `apps/api/app/domain/models.py`
- Create: `apps/api/app/db/migrations/versions/20260515_family_test_llm_student_usage.py`
- Modify: `apps/api/app/core/config.py`
- Modify: `.env-sample`
- Modify: `apps/api/app/services/ai_tasks.py`
- Modify: `apps/api/app/api/routes/essays.py`
- Modify: `apps/api/tests/test_domain_models.py`
- Modify: `apps/api/tests/test_migrations.py`
- Modify: `apps/api/tests/test_llm_logging.py`
- Modify: `apps/api/tests/test_ai_task_resilience.py`
- Modify: `apps/api/tests/test_essay_workflow_api.py`

- [ ] **Step 1: Add failing model and logging tests**

Append to `apps/api/tests/test_domain_models.py`:

```python
from app.domain.enums import TaskType
from app.domain.models import LLMCallLog


def test_llm_call_log_tracks_student_and_task_name():
    log = LLMCallLog(
        student_id="s1",
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        provider="http",
        model="test-model",
        prompt_version="v0.2-family-test-2026-05-15",
        input_summary="句子快练；原句长度：5；升级句长度：18",
        raw_response='{"encouragement":"写清楚了"}',
        output_json={"encouragement": "写清楚了"},
        validation_ok=True,
        error_message="",
        retry_count=0,
    )

    assert log.student_id == "s1"
    assert log.task_name == "sentence_upgrade_feedback"
```

Update `apps/api/tests/test_llm_logging.py` so `log_llm_result(...)` receives and verifies `student_id` and `task_name`:

```python
    log_llm_result(
        session=session,
        student_id="s1",
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        provider="mock",
        model="mock",
        prompt_version="test-v1",
        input_summary="学生把句子改得更生动",
        raw_response='{"specific_improvement":"把画面写得更具体"}',
        output_json={"specific_improvement": improvement},
        validation_ok=True,
        error_message="",
        retry_count=0,
    )
```

Add these assertions after `saved = session.exec(select(LLMCallLog)).one()`:

```python
    assert saved.student_id == "s1"
    assert saved.task_name == "sentence_upgrade_feedback"
```

- [ ] **Step 2: Add failing migration and essay log-context tests**

Append to `apps/api/tests/test_migrations.py`:

```python
def test_family_test_llm_student_usage_has_migration():
    versions_dir = Path("app/db/migrations/versions")
    migration_text = "\n".join(path.read_text(encoding="utf-8") for path in versions_dir.glob("*.py"))

    assert "20260515_family_test_llm_student_usage" in migration_text
    assert "llmcalllog" in migration_text
    assert "student_id" in migration_text
    assert "task_name" in migration_text
```

In `apps/api/tests/test_essay_workflow_api.py`, import `LLMCallLog`:

```python
from app.domain.models import Essay, EssayVersion, GameEvent, LLMCallLog, StudentProfile
```

In `test_essay_from_existing_draft_feedback_and_revision`, after `saved_revision = ...`, add:

```python
    logs = session.exec(select(LLMCallLog).where(LLMCallLog.student_id == student.id)).all()
    assert {log.task_name for log in logs} == {"essay_feedback", "essay_revision_comparison"}
    assert {log.task_type for log in logs} == {TaskType.essay}
```

- [ ] **Step 3: Add failing daily-limit test**

Append to `apps/api/tests/test_ai_task_resilience.py`:

```python
class CountingRealProvider:
    provider_name = "http"
    model_name = "limit-test-model"

    def __init__(self):
        self.calls = 0

    async def complete_json(self, task_name, payload):
        self.calls += 1
        parsed = {
            "strengths": ["能写清楚发生了什么", "有一处心情表达"],
            "improvements": ["第二段缺少动作细节"],
            "problem_monsters": ["细节缺口"],
            "sentence_notes": ["把开心换成具体画面。"],
            "revision_tasks": [
                {"instruction": "给第二段加一个动作描写", "target": "第二段"}
            ],
        }
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


@pytest.mark.asyncio
async def test_daily_limit_returns_fallback_without_calling_real_provider_again(session):
    provider = CountingRealProvider()

    first = await essay_feedback(
        provider=provider,
        title="我学会了骑车",
        draft="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
        session=session,
        prompt_version="test-v1",
        student_id="s1",
        daily_limit_enabled=True,
        daily_limit_per_student_task=1,
    )
    second = await essay_feedback(
        provider=provider,
        title="我学会了骑车",
        draft="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
        session=session,
        prompt_version="test-v1",
        student_id="s1",
        daily_limit_enabled=True,
        daily_limit_per_student_task=1,
    )

    logs = session.exec(select(LLMCallLog).where(LLMCallLog.student_id == "s1")).all()
    assert provider.calls == 1
    assert first.output.revision_tasks[0].instruction == "给第二段加一个动作描写"
    assert second.output.revision_tasks[0].instruction == "先给最重要的一段加一个动作或看到的细节"
    assert len(logs) == 2
    assert logs[-1].validation_ok is False
    assert logs[-1].error_message == "daily limit exceeded"
```

- [ ] **Step 4: Run tests and confirm they fail**

Run:

```powershell
cd apps/api
uv run pytest tests/test_domain_models.py tests/test_migrations.py tests/test_llm_logging.py tests/test_ai_task_resilience.py tests/test_essay_workflow_api.py -q
```

Expected: FAIL because `student_id`, `task_name`, usage settings, and daily-limit logic are not present.

- [ ] **Step 5: Add model fields**

In `apps/api/app/domain/models.py`, replace `LLMCallLog` with:

```python
class LLMCallLog(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str | None = Field(default=None, foreign_key="studentprofile.id", index=True)
    task_type: TaskType
    task_name: str = Field(default="unknown", index=True)
    provider: str = "mock"
    model: str = "mock"
    prompt_version: str = "v0.2-quality-spine-2026-05-14"
    input_summary: str
    raw_response: str = ""
    output_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    validation_ok: bool = False
    error_message: str = ""
    retry_count: int = 0
    created_at: datetime = timestamp_field()
```

- [ ] **Step 6: Add migration**

Create `apps/api/app/db/migrations/versions/20260515_family_test_llm_student_usage.py`:

```python
"""Add student LLM traceability and task name."""

import sqlalchemy as sa
from alembic import op


revision = "20260515_family_test_llm_student_usage"
down_revision = "20260514_quality_spine_logging_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llmcalllog", sa.Column("student_id", sa.String(), nullable=True))
    op.add_column(
        "llmcalllog",
        sa.Column("task_name", sa.String(), nullable=False, server_default="unknown"),
    )
    op.create_foreign_key(
        "fk_llmcalllog_student_id_studentprofile",
        "llmcalllog",
        "studentprofile",
        ["student_id"],
        ["id"],
    )
    op.create_index("ix_llmcalllog_student_id", "llmcalllog", ["student_id"], unique=False)
    op.create_index("ix_llmcalllog_task_name", "llmcalllog", ["task_name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_llmcalllog_task_name", table_name="llmcalllog")
    op.drop_index("ix_llmcalllog_student_id", table_name="llmcalllog")
    op.drop_constraint(
        "fk_llmcalllog_student_id_studentprofile",
        "llmcalllog",
        type_="foreignkey",
    )
    op.drop_column("llmcalllog", "task_name")
    op.drop_column("llmcalllog", "student_id")
```

- [ ] **Step 7: Add disabled-by-default settings**

In `apps/api/app/core/config.py`, add:

```python
    llm_daily_limit_enabled: bool = False
    llm_daily_limit_per_student_task: int = 5
```

In `.env-sample`, add:

```text
LLM_DAILY_LIMIT_ENABLED=false
LLM_DAILY_LIMIT_PER_STUDENT_TASK=5
```

- [ ] **Step 8: Update `ai_tasks.py` logging and usage limit**

In `apps/api/app/services/ai_tasks.py`, add imports:

```python
from datetime import datetime, time, timezone

from sqlalchemy import func
from sqlmodel import select
```

Replace `log_llm_result(...)` with:

```python
def log_llm_result(
    session: Session,
    task_type: TaskType,
    provider: str,
    model: str,
    prompt_version: str,
    input_summary: str,
    raw_response: str,
    output_json: dict,
    validation_ok: bool,
    error_message: str,
    retry_count: int,
    student_id: str | None = None,
    task_name: str = "unknown",
) -> LLMCallLog:
    log = LLMCallLog(
        student_id=student_id,
        task_type=task_type,
        task_name=task_name,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        input_summary=input_summary,
        raw_response=raw_response,
        output_json=output_json,
        validation_ok=validation_ok,
        error_message=error_message,
        retry_count=retry_count,
    )
    session.add(log)
    session.flush()
    return log
```

Add these helpers below `fallback_revision_comparison()`:

```python
def _start_of_utc_day() -> datetime:
    today = datetime.now(timezone.utc).date()
    return datetime.combine(today, time.min, tzinfo=timezone.utc)


def _is_real_provider(provider_name: str) -> bool:
    return provider_name.strip().lower() not in {"", "mock"}


def _daily_log_count(session: Session, student_id: str, task_name: str) -> int:
    count = session.exec(
        select(func.count(LLMCallLog.id)).where(
            LLMCallLog.student_id == student_id,
            LLMCallLog.task_name == task_name,
            LLMCallLog.created_at >= _start_of_utc_day(),
            LLMCallLog.error_message != "daily limit exceeded",
        )
    ).one()
    return int(count)
```

Update `run_validated_llm_task(...)` parameters:

```python
    student_id: str | None = None,
    daily_limit_enabled: bool = False,
    daily_limit_per_student_task: int = 5,
```

Inside `run_validated_llm_task(...)`, after provider/model names are initialized and before the retry loop, add:

```python
    if (
        daily_limit_enabled
        and session is not None
        and student_id is not None
        and _is_real_provider(provider_name)
        and _daily_log_count(session, student_id, task_name) >= daily_limit_per_student_task
    ):
        log = log_llm_result(
            session=session,
            student_id=student_id,
            task_type=task_type,
            task_name=task_name,
            provider=provider_name,
            model=model_name,
            prompt_version=prompt_version,
            input_summary=input_summary,
            raw_response="",
            output_json=fallback.model_dump(),
            validation_ok=False,
            error_message="daily limit exceeded",
            retry_count=0,
        )
        return LLMTaskResult(output=fallback, log=log)
```

In both success and fallback calls to `log_llm_result(...)` inside `run_validated_llm_task(...)`, pass:

```python
                    student_id=student_id,
                    task_name=task_name,
```

- [ ] **Step 9: Pass student context from essay tasks and routes**

Update `essay_feedback(...)` signature:

```python
async def essay_feedback(
    provider: LLMProvider,
    title: str,
    draft: str,
    session: Session | None = None,
    prompt_version: str = "v0.2-quality-spine-2026-05-14",
    student_id: str | None = None,
    daily_limit_enabled: bool = False,
    daily_limit_per_student_task: int = 5,
) -> LLMTaskResult[EssayFeedback]:
```

Pass these into `run_validated_llm_task(...)`:

```python
        student_id=student_id,
        daily_limit_enabled=daily_limit_enabled,
        daily_limit_per_student_task=daily_limit_per_student_task,
```

Update `essay_revision_comparison(...)` the same way and pass the same three arguments into `run_validated_llm_task(...)`.

In `apps/api/app/api/routes/essays.py`, update the `essay_feedback(...)` call:

```python
        feedback_result = await essay_feedback(
            provider,
            request.title,
            request.draft,
            session=session,
            prompt_version=settings.llm_prompt_version,
            student_id=student_id,
            daily_limit_enabled=settings.llm_daily_limit_enabled,
            daily_limit_per_student_task=settings.llm_daily_limit_per_student_task,
        )
```

Update the `essay_revision_comparison(...)` call:

```python
    comparison_result = await essay_revision_comparison(
        provider,
        first_draft.content,
        request.content,
        session=session,
        prompt_version=settings.llm_prompt_version,
        student_id=essay.student_id,
        daily_limit_enabled=settings.llm_daily_limit_enabled,
        daily_limit_per_student_task=settings.llm_daily_limit_per_student_task,
    )
```

- [ ] **Step 10: Verify Task 1**

Run:

```powershell
cd apps/api
uv run pytest tests/test_domain_models.py tests/test_migrations.py tests/test_llm_logging.py tests/test_ai_task_resilience.py tests/test_essay_workflow_api.py -q
```

Expected: PASS.

- [ ] **Step 11: Review gate and commit**

Review:

```powershell
git diff -- apps/api/app/domain/models.py apps/api/app/db/migrations/versions/20260515_family_test_llm_student_usage.py apps/api/app/core/config.py .env-sample apps/api/app/services/ai_tasks.py apps/api/app/api/routes/essays.py apps/api/tests/test_domain_models.py apps/api/tests/test_migrations.py apps/api/tests/test_llm_logging.py apps/api/tests/test_ai_task_resilience.py apps/api/tests/test_essay_workflow_api.py
```

Commit:

```powershell
git add apps/api/app/domain/models.py apps/api/app/db/migrations/versions/20260515_family_test_llm_student_usage.py apps/api/app/core/config.py .env-sample apps/api/app/services/ai_tasks.py apps/api/app/api/routes/essays.py apps/api/tests/test_domain_models.py apps/api/tests/test_migrations.py apps/api/tests/test_llm_logging.py apps/api/tests/test_ai_task_resilience.py apps/api/tests/test_essay_workflow_api.py
git commit -m "feat: add student llm traceability and limits"
```

---

### Task 2: Upgrade Sentence AI To The Shared Quality Spine

**Files:**
- Modify: `apps/api/app/services/ai_tasks.py`
- Modify: `apps/api/app/api/routes/sentences.py`
- Modify: `apps/api/tests/test_ai_task_resilience.py`
- Modify: `apps/api/tests/test_llm_contracts.py`
- Modify: `apps/api/tests/test_llm_provider_dependency.py`
- Modify: `apps/api/tests/test_sentence_training_api.py`

- [ ] **Step 1: Add failing sentence resilience tests**

In `apps/api/tests/test_ai_task_resilience.py`, add:

```python
class InvalidSentenceThenValidProvider:
    provider_name = "fake"
    model_name = "sentence-invalid-then-valid"

    def __init__(self):
        self.calls = 0

    async def complete_json(self, task_name, payload):
        self.calls += 1
        if self.calls == 1:
            parsed = {
                "encouragement": "不错",
                "specific_improvement": "",
                "next_step": "继续练习",
                "ability_delta": {"expression": 4},
                "problem_monsters": ["空泛表达"],
            }
        else:
            parsed = {
                "encouragement": "你把画面写得更清楚了。",
                "specific_improvement": "加入了可看见的细节",
                "next_step": "再加一个动作，会更生动。",
                "ability_delta": {"expression": 4, "observation": 4},
                "problem_monsters": ["空泛表达"],
            }
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


class AlwaysInvalidSentenceProvider:
    provider_name = "fake"
    model_name = "sentence-always-invalid"

    async def complete_json(self, task_name, payload):
        parsed = {
            "encouragement": "",
            "specific_improvement": "",
            "next_step": "",
            "ability_delta": {},
            "problem_monsters": [],
        }
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


@pytest.mark.asyncio
async def test_sentence_invalid_then_valid_retries_and_logs_success(session):
    provider = InvalidSentenceThenValidProvider()

    result = await sentence_upgrade_feedback(
        provider=provider,
        source_sentence="公园很美。",
        upgraded_sentence="清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
        focus="加细节",
        session=session,
        prompt_version="test-v1",
        student_id="s1",
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert provider.calls == 2
    assert result.output.specific_improvement == "加入了可看见的细节"
    assert saved.student_id == "s1"
    assert saved.task_name == "sentence_upgrade_feedback"
    assert saved.validation_ok is True
    assert saved.retry_count == 1


@pytest.mark.asyncio
async def test_sentence_always_invalid_returns_schema_valid_fallback(session):
    result = await sentence_upgrade_feedback(
        provider=AlwaysInvalidSentenceProvider(),
        source_sentence="公园很美。",
        upgraded_sentence="公园的花在风里轻轻摇。",
        focus="加细节",
        session=session,
        prompt_version="test-v1",
        student_id="s1",
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert result.output.encouragement == "你已经完成了一次句子升级。"
    assert result.output.specific_improvement == "先把一个看得见的细节写清楚"
    assert result.output.problem_monsters == ["空泛表达"]
    assert saved.validation_ok is False
    assert "validation" in saved.error_message.lower()
```

Add `sentence_upgrade_feedback` to the import list at the top of `test_ai_task_resilience.py`.

- [ ] **Step 2: Add failing sentence route DI test**

Append to `apps/api/tests/test_llm_provider_dependency.py`:

```python
class RecordingSentenceProvider:
    provider_name = "fake-sentence-provider"
    model_name = "fake-sentence-model"

    def __init__(self):
        self.calls: list[str] = []

    async def complete_json(self, task_name, payload):
        self.calls.append(task_name)
        parsed = {
            "encouragement": "你把画面写得更清楚了。",
            "specific_improvement": "加入了可看见的细节",
            "next_step": "再加一个动作，会更生动。",
            "ability_delta": {"expression": 4, "observation": 4},
            "problem_monsters": ["空泛表达"],
        }
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


def test_sentence_route_uses_provider_dependency_override_and_logs_student_context(session, client):
    parent = seed_demo_data(session)
    student = session.exec(
        select(StudentProfile).where(StudentProfile.parent_id == parent.id)
    ).first()
    provider = RecordingSentenceProvider()
    client.app.dependency_overrides[get_llm_provider] = lambda: provider

    response = client.post(
        f"/api/students/{student.id}/sentences",
        json={
            "source_sentence": "公园很美。",
            "upgraded_sentence": "清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
            "focus": "加细节",
        },
    )

    logs = session.exec(select(LLMCallLog).where(LLMCallLog.student_id == student.id)).all()
    assert response.status_code == 201
    assert provider.calls == ["sentence_upgrade_feedback"]
    assert logs[0].task_name == "sentence_upgrade_feedback"
    assert logs[0].provider == "fake-sentence-provider"
```

Add `LLMCallLog` to the model imports in that file.

- [ ] **Step 3: Run tests and confirm they fail**

Run:

```powershell
cd apps/api
uv run pytest tests/test_ai_task_resilience.py tests/test_llm_contracts.py tests/test_llm_provider_dependency.py tests/test_sentence_training_api.py -q
```

Expected: FAIL because sentence feedback still returns `SentenceFeedback` directly and the sentence route still instantiates `MockLLMProvider()`.

- [ ] **Step 4: Add sentence fallback and shared runner**

In `apps/api/app/services/ai_tasks.py`, add below `fallback_revision_comparison()`:

```python
def fallback_sentence_feedback() -> SentenceFeedback:
    return SentenceFeedback(
        encouragement="你已经完成了一次句子升级。",
        specific_improvement="先把一个看得见的细节写清楚",
        next_step="再读一遍你的句子，圈出一个动作、声音或颜色细节。",
        ability_delta={"expression": 2, "observation": 2},
        problem_monsters=["空泛表达"],
    )
```

Replace `sentence_upgrade_feedback(...)` with:

```python
async def sentence_upgrade_feedback(
    provider: LLMProvider,
    source_sentence: str,
    upgraded_sentence: str,
    focus: str,
    session: Session | None = None,
    prompt_version: str = "v0.2-quality-spine-2026-05-14",
    student_id: str | None = None,
    daily_limit_enabled: bool = False,
    daily_limit_per_student_task: int = 5,
) -> LLMTaskResult[SentenceFeedback]:
    return await run_validated_llm_task(
        provider=provider,
        session=session,
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        payload={
            "source_sentence": source_sentence,
            "upgraded_sentence": upgraded_sentence,
            "focus": focus,
        },
        output_model=SentenceFeedback,
        fallback=fallback_sentence_feedback(),
        input_summary=(
            f"句子快练；原句长度：{len(source_sentence)}；"
            f"升级句长度：{len(upgraded_sentence)}；目标：{focus}"
        ),
        prompt_version=prompt_version,
        student_id=student_id,
        daily_limit_enabled=daily_limit_enabled,
        daily_limit_per_student_task=daily_limit_per_student_task,
    )
```

- [ ] **Step 5: Update sentence route to use DI and settings**

In `apps/api/app/api/routes/sentences.py`, replace imports:

```python
from app.api.deps import get_db_session, get_llm_provider
from app.core.config import Settings, get_settings
from app.services.llm_provider import LLMProvider
```

Remove:

```python
from app.services.llm_provider import MockLLMProvider
```

Update route parameters:

```python
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
```

Replace the feedback call:

```python
    feedback_result = await sentence_upgrade_feedback(
        provider=provider,
        source_sentence=request.source_sentence,
        upgraded_sentence=request.upgraded_sentence,
        focus=request.focus,
        session=session,
        prompt_version=settings.llm_prompt_version,
        student_id=student_id,
        daily_limit_enabled=settings.llm_daily_limit_enabled,
        daily_limit_per_student_task=settings.llm_daily_limit_per_student_task,
    )
    feedback = feedback_result.output
```

- [ ] **Step 6: Update sentence contract tests for result wrapper**

In `apps/api/tests/test_llm_contracts.py`, update `test_sentence_upgrade_feedback_uses_structured_mock_provider`:

```python
    assert result.output.specific_improvement == "加入了可看见的细节"
    assert result.output.ability_delta["expression"] == 4
    assert result.output.problem_monsters == ["空泛表达"]
    assert result.log is None
```

Replace `test_sentence_upgrade_feedback_rejects_malformed_provider_response` with:

```python
@pytest.mark.asyncio
async def test_sentence_upgrade_feedback_returns_fallback_for_malformed_provider_response():
    result = await sentence_upgrade_feedback(
        provider=MalformedSentenceProvider(),
        source_sentence="公园很美。",
        upgraded_sentence="清晨的公园里，荷叶上的水珠一闪一闪。",
        focus="加细节",
    )

    assert result.output.encouragement == "你已经完成了一次句子升级。"
    assert result.output.specific_improvement == "先把一个看得见的细节写清楚"
    assert result.log is None
```

- [ ] **Step 7: Verify Task 2**

Run:

```powershell
cd apps/api
uv run pytest tests/test_ai_task_resilience.py tests/test_llm_contracts.py tests/test_llm_provider_dependency.py tests/test_sentence_training_api.py -q
```

Expected: PASS.

- [ ] **Step 8: Review gate and commit**

Review:

```powershell
git diff -- apps/api/app/services/ai_tasks.py apps/api/app/api/routes/sentences.py apps/api/tests/test_ai_task_resilience.py apps/api/tests/test_llm_contracts.py apps/api/tests/test_llm_provider_dependency.py apps/api/tests/test_sentence_training_api.py
```

Commit:

```powershell
git add apps/api/app/services/ai_tasks.py apps/api/app/api/routes/sentences.py apps/api/tests/test_ai_task_resilience.py apps/api/tests/test_llm_contracts.py apps/api/tests/test_llm_provider_dependency.py apps/api/tests/test_sentence_training_api.py
git commit -m "feat: upgrade sentence ai quality spine"
```

---

### Task 3: Tighten Essay Prompt, Default Task Selection, And Settlement Count

**Files:**
- Modify: `apps/api/app/services/llm_provider.py`
- Modify: `apps/api/app/api/routes/essays.py`
- Modify: `apps/api/tests/test_llm_contracts.py`
- Modify: `apps/api/tests/test_essay_workflow_api.py`
- Modify: `apps/web/src/app/children/[studentId]/essay/page.tsx`
- Modify: `apps/web/src/components/SettlementPanel.tsx`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/tests/essay_reading_report_flow.test.tsx`

- [ ] **Step 1: Add failing prompt contract and settlement evidence tests**

In `apps/api/tests/test_llm_contracts.py`, import:

```python
from app.services.llm_provider import LLMProviderResponse, MockLLMProvider, response_contract_for_task
```

Append:

```python
def test_essay_feedback_provider_contract_prefers_exactly_one_revision_task():
    contract = response_contract_for_task("essay_feedback")

    assert "revision_tasks: array of exactly 1 object" in contract
    assert "Do not write a full essay" in contract
```

In `apps/api/tests/test_essay_workflow_api.py`, inside `test_essay_from_existing_draft_feedback_and_revision`, after the `GameEvent` assertion, replace:

```python
    assert session.exec(select(GameEvent)).one().xp_delta == 60
```

with:

```python
    event = session.exec(select(GameEvent)).one()
    assert event.xp_delta == 60
    assert event.evidence["completed_task_count"] == 1
    assert event.evidence["completed_tasks"] == ["给第二段加一个动作描写"]
```

- [ ] **Step 2: Add failing frontend default-selection test**

In `apps/web/tests/essay_reading_report_flow.test.tsx`, remove the manual checkbox click:

```tsx
  await userEvent.click(
    screen.getByRole("checkbox", { name: "给第二段加一个动作描写" }),
  );
```

After `expect(await screen.findByText("给第二段加一个动作描写")).toBeInTheDocument();`, add:

```tsx
  expect(
    screen.getByRole("checkbox", { name: "给第二段加一个动作描写" }),
  ).toBeChecked();
```

In the mocked revision response, include settlement evidence:

```tsx
    settlement: {
      xp_delta: 60,
      level_after: 2,
      badge_code: "first_revision",
      evidence: { completed_task_count: 1 },
    },
```

After `expect(await screen.findByText("细节更多")).toBeInTheDocument();`, add:

```tsx
  expect(screen.getByText("完成 1 个修改任务")).toBeInTheDocument();
```

- [ ] **Step 3: Run tests and confirm they fail**

Run:

```powershell
cd apps/api
uv run pytest tests/test_llm_contracts.py tests/test_essay_workflow_api.py -q
cd ../web
pnpm exec vitest run tests/essay_reading_report_flow.test.tsx --environment jsdom
```

Expected: FAIL because the provider contract still says 1 to 3 revision tasks, the UI leaves tasks unselected, and settlement does not render completed task count.

- [ ] **Step 4: Tighten provider contract without narrowing the schema**

In `apps/api/app/services/llm_provider.py`, replace the `essay_feedback` contract text with:

```python
    "essay_feedback": (
        "Return a JSON object with exactly these fields: "
        "strengths: array of exactly 2 non-empty strings; "
        "improvements: array of 1 to 3 non-empty strings; "
        "problem_monsters: array of 1 to 3 non-empty strings; "
        "sentence_notes: array of 1 to 3 non-empty strings; "
        "revision_tasks: array of exactly 1 object with non-empty "
        "instruction and target strings. Pick the smallest and most important revision task. "
        "Do not write a full essay."
    ),
```

Keep `EssayFeedback.revision_tasks` at `Field(min_length=1, max_length=3)` so valid provider responses with more than one task do not block the child.

- [ ] **Step 5: Persist completed task count in settlement evidence**

In `apps/api/app/api/routes/essays.py`, replace the essay `settle_task(...)` call:

```python
    event = settle_task(student, TaskType.essay, ["细节缺口"], {"essay_id": essay_id})
```

with:

```python
    event = settle_task(
        student,
        TaskType.essay,
        ["细节缺口"],
        {
            "essay_id": essay_id,
            "completed_task_count": len(request.completed_tasks),
            "completed_tasks": request.completed_tasks,
        },
    )
```

- [ ] **Step 6: Default essay revision tasks to selected**

In `apps/web/src/app/children/[studentId]/essay/page.tsx`, replace:

```tsx
      setSelectedTasks([]);
```

with:

```tsx
      setSelectedTasks(result.feedback.revision_tasks.map((task) => task.instruction));
```

- [ ] **Step 7: Render completed task count in settlement**

In `apps/web/src/lib/api.ts`, update `Settlement`:

```ts
export type Settlement = {
  xp_delta: number;
  level_after: number;
  badge_code?: string;
  evidence?: {
    completed_task_count?: number;
    completed_tasks?: string[];
    [key: string]: unknown;
  };
};
```

In `apps/web/src/components/SettlementPanel.tsx`, add:

```tsx
        {typeof settlement.evidence?.completed_task_count === "number" ? (
          <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-2 font-semibold">
            完成 {settlement.evidence.completed_task_count} 个修改任务
          </p>
        ) : null}
```

Place it after the level badge and before `badge_code`.

- [ ] **Step 8: Verify Task 3**

Run:

```powershell
cd apps/api
uv run pytest tests/test_llm_contracts.py tests/test_essay_workflow_api.py -q
cd ../web
pnpm exec vitest run tests/essay_reading_report_flow.test.tsx --environment jsdom
```

Expected: PASS.

- [ ] **Step 9: Review gate and commit**

Review:

```powershell
git diff -- apps/api/app/services/llm_provider.py apps/api/app/api/routes/essays.py apps/api/tests/test_llm_contracts.py apps/api/tests/test_essay_workflow_api.py apps/web/src/app/children/[studentId]/essay/page.tsx apps/web/src/components/SettlementPanel.tsx apps/web/src/lib/api.ts apps/web/tests/essay_reading_report_flow.test.tsx
```

Commit:

```powershell
git add apps/api/app/services/llm_provider.py apps/api/app/api/routes/essays.py apps/api/tests/test_llm_contracts.py apps/api/tests/test_essay_workflow_api.py apps/web/src/app/children/[studentId]/essay/page.tsx apps/web/src/components/SettlementPanel.tsx apps/web/src/lib/api.ts apps/web/tests/essay_reading_report_flow.test.tsx
git commit -m "feat: tighten essay task completion flow"
```

---

### Task 4: Add Family Topbar, Child Switcher, And Connected Task Entries

**Files:**
- Create: `apps/web/src/components/FamilyTopbar.tsx`
- Modify: `apps/web/src/app/children/[studentId]/page.tsx`
- Modify: `apps/web/src/app/children/[studentId]/essay/page.tsx`
- Modify: `apps/web/src/app/children/[studentId]/sentence/page.tsx`
- Modify: `apps/web/src/app/children/[studentId]/reading/page.tsx`
- Modify: `apps/web/src/app/parent/[studentId]/report/page.tsx`
- Modify: `apps/web/src/components/TaskCards.tsx`
- Modify: `apps/web/tests/dashboard.test.tsx`
- Modify: `apps/web/tests/assessment_sentence_flow.test.tsx`
- Modify: `apps/web/tests/essay_reading_report_flow.test.tsx`
- Create: `apps/web/tests/family_topbar.test.tsx`

- [ ] **Step 1: Add failing FamilyTopbar test**

Create `apps/web/tests/family_topbar.test.tsx`:

```tsx
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { FamilyTopbar } from "../src/components/FamilyTopbar";

const apiMocks = vi.hoisted(() => ({
  demoLogin: vi.fn(),
}));

vi.mock("../src/lib/api", () => ({
  demoLogin: apiMocks.demoLogin,
}));

test("renders current child, primary nav, and child switcher links", async () => {
  apiMocks.demoLogin.mockResolvedValue({
    parent: { id: "p1", email: "demo@wenlingo.local", display_name: "内测家长" },
    students: [
      { id: "s2", name: "小晴", grade_label: "四年级", persona: "vague_expression", level: 1, xp: 0 },
      { id: "s1", name: "小宇", grade_label: "四年级", persona: "real_child", level: 2, xp: 115 },
    ],
  });

  render(<FamilyTopbar currentStudentId="s1" />);

  expect(await screen.findByText("当前孩子：小宇")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "小文星球" })).toHaveAttribute("href", "/children/s1");
  expect(screen.getByRole("link", { name: "作文城堡" })).toHaveAttribute("href", "/children/s1/essay");
  expect(screen.getByRole("link", { name: "句子工坊" })).toHaveAttribute("href", "/children/s1/sentence");
  expect(screen.getByRole("link", { name: "家长报告" })).toHaveAttribute("href", "/parent/s1/report");
  expect(screen.getByRole("link", { name: "小晴" })).toHaveAttribute("href", "/children/s2");
});
```

- [ ] **Step 2: Add failing dashboard task-card label assertion**

In `apps/web/tests/dashboard.test.tsx`, extend the mocked API module so it includes `demoLogin` for `FamilyTopbar`:

```tsx
vi.mock("../src/lib/api", () => ({
  demoLogin: vi.fn(async () => ({
    parent: { id: "p1", email: "demo@wenlingo.local", display_name: "内测家长" },
    students: [
      { id: "s1", name: "小宇", grade_label: "四年级", persona: "real_child", level: 2, xp: 115 },
      { id: "s2", name: "小晴", grade_label: "四年级", persona: "vague_expression", level: 1, xp: 0 },
      { id: "s3", name: "小川", grade_label: "四年级", persona: "weak_structure", level: 1, xp: 0 },
      { id: "s4", name: "小禾", grade_label: "四年级", persona: "weak_reading_summary", level: 1, xp: 0 },
    ],
  })),
  getDashboard: vi.fn(async () => ({
    student: {
      id: "s1",
      name: "小宇",
      grade_label: "四年级",
      persona: "real_child",
      level: 2,
      xp: 115,
    },
    ability_note: "第一张能力草图",
    child_abilities: {
      reading_power: 50,
      specific_writing_power: 54,
      revision_power: 20,
    },
    today_tasks: {
      main: {
        kind: "essay",
        title: "作文城堡",
        focus: "把细节写具体",
        minutes: "10-15",
      },
      quick: {
        kind: "sentence",
        title: "句子工坊",
        focus: "加细节",
        minutes: "5-8",
      },
    },
    map: ["句子工坊", "作文城堡", "阅读峡谷"],
    coach_message: "今天先完成推荐任务，再看看哪里变强了。",
  })),
}));
```

Then add:

```tsx
  expect(screen.getByRole("heading", { name: "作文城堡" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "主线：作文城堡" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /开始任务/ })).toHaveAttribute(
    "href",
    "/children/s1/sentence",
  );
```

- [ ] **Step 3: Add topbar API mocks to page tests**

In `apps/web/tests/assessment_sentence_flow.test.tsx`, extend `apiMocks`:

```tsx
const apiMocks = vi.hoisted(() => ({
  createAssessment: vi.fn(),
  createSentenceTraining: vi.fn(),
  demoLogin: vi.fn(),
}));
```

Extend the mocked module:

```tsx
vi.mock("../src/lib/api", () => ({
  createAssessment: apiMocks.createAssessment,
  createSentenceTraining: apiMocks.createSentenceTraining,
  demoLogin: apiMocks.demoLogin,
}));
```

In `beforeEach`, add:

```tsx
  apiMocks.demoLogin.mockResolvedValue({
    parent: { id: "p1", email: "demo@wenlingo.local", display_name: "内测家长" },
    students: [
      { id: "s1", name: "小宇", grade_label: "四年级", persona: "real_child", level: 2, xp: 115 },
      { id: "s2", name: "小晴", grade_label: "四年级", persona: "vague_expression", level: 1, xp: 0 },
      { id: "s3", name: "小川", grade_label: "四年级", persona: "weak_structure", level: 1, xp: 0 },
      { id: "s4", name: "小禾", grade_label: "四年级", persona: "weak_reading_summary", level: 1, xp: 0 },
    ],
  });
```

In `apps/web/tests/essay_reading_report_flow.test.tsx`, extend `apiMocks` and the module mock the same way, preserving its existing `createEssay`, `submitEssayRevision`, `createReadingSession`, and `createReport` mocks.

- [ ] **Step 4: Run tests and confirm they fail**

Run:

```powershell
cd apps/web
pnpm exec vitest run tests/family_topbar.test.tsx tests/dashboard.test.tsx tests/assessment_sentence_flow.test.tsx tests/essay_reading_report_flow.test.tsx --environment jsdom
```

Expected: FAIL because `FamilyTopbar` does not exist and `TaskCards` still duplicates the section label in the task title.

- [ ] **Step 5: Create FamilyTopbar**

Create `apps/web/src/components/FamilyTopbar.tsx`:

```tsx
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { demoLogin } from "../lib/api";
import type { Student } from "../lib/types";

export function FamilyTopbar({ currentStudentId }: { currentStudentId: string }) {
  const [students, setStudents] = useState<Student[]>([]);

  useEffect(() => {
    let isMounted = true;
    demoLogin()
      .then((result) => {
        if (isMounted) {
          setStudents(result.students);
        }
      })
      .catch(() => {
        if (isMounted) {
          setStudents([]);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const sortedStudents = useMemo(
    () => [...students].sort((first, second) => first.id.localeCompare(second.id)),
    [students],
  );
  const currentStudent = sortedStudents.find((student) => student.id === currentStudentId);

  return (
    <header className="border-b border-[var(--wen-border)] bg-white/85 px-5 py-3 shadow-sm backdrop-blur sm:px-8">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3">
        <Link href={`/children/${currentStudentId}`} className="text-lg font-bold">
          小文星球
        </Link>
        <p className="font-semibold text-[var(--wen-muted)]">
          当前孩子：{currentStudent?.name ?? currentStudentId}
        </p>
        <nav aria-label="主导航" className="flex flex-wrap gap-2">
          <Link className="rounded-lg px-3 py-2 font-semibold hover:bg-[var(--wen-bg)]" href={`/children/${currentStudentId}`}>
            Dashboard
          </Link>
          <Link className="rounded-lg px-3 py-2 font-semibold hover:bg-[var(--wen-bg)]" href={`/children/${currentStudentId}/essay`}>
            作文城堡
          </Link>
          <Link className="rounded-lg px-3 py-2 font-semibold hover:bg-[var(--wen-bg)]" href={`/children/${currentStudentId}/sentence`}>
            句子工坊
          </Link>
          <Link className="rounded-lg px-3 py-2 font-semibold hover:bg-[var(--wen-bg)]" href={`/parent/${currentStudentId}/report`}>
            家长报告
          </Link>
        </nav>
        {sortedStudents.length > 0 ? (
          <nav aria-label="孩子切换" className="ml-auto flex flex-wrap gap-2">
            {sortedStudents.map((student) => (
              <Link
                key={student.id}
                aria-current={student.id === currentStudentId ? "page" : undefined}
                href={`/children/${student.id}`}
                className="rounded-lg border border-[var(--wen-border)] px-3 py-2 font-semibold aria-[current=page]:border-[var(--wen-orange)] aria-[current=page]:text-[var(--wen-orange)]"
              >
                {student.name}
              </Link>
            ))}
          </nav>
        ) : null}
      </div>
    </header>
  );
}
```

- [ ] **Step 6: Add topbar to main family-test pages**

In each of these files, import `FamilyTopbar` and render it before `<main>`:

- `apps/web/src/app/children/[studentId]/page.tsx`
- `apps/web/src/app/children/[studentId]/essay/page.tsx`
- `apps/web/src/app/children/[studentId]/sentence/page.tsx`
- `apps/web/src/app/children/[studentId]/reading/page.tsx`
- `apps/web/src/app/parent/[studentId]/report/page.tsx`

Use this shape:

```tsx
import { FamilyTopbar } from "../../../components/FamilyTopbar";
```

For dashboard, the relative path is:

```tsx
import { FamilyTopbar } from "../../../components/FamilyTopbar";
```

For essay, sentence, reading, and report pages, use:

```tsx
import { FamilyTopbar } from "../../../../components/FamilyTopbar";
```

Wrap return values:

```tsx
  return (
    <>
      <FamilyTopbar currentStudentId={studentId} />
      <main className="min-h-screen px-5 py-8 sm:px-8">
        ...
      </main>
    </>
  );
```

- [ ] **Step 7: Remove duplicate task labels and ensure task links**

In `apps/web/src/components/TaskCards.tsx`, replace:

```tsx
              <h3 className="mt-1 text-lg font-bold">
                {label}：{task.title}
              </h3>
```

with:

```tsx
              <h3 className="mt-1 text-lg font-bold">{task.title}</h3>
```

Keep the existing `href` logic:

```tsx
          const href =
            task.kind === "essay"
              ? `/children/${studentId}/essay`
              : `/children/${studentId}/${task.kind}`;
```

- [ ] **Step 8: Verify Task 4**

Run:

```powershell
cd apps/web
pnpm exec vitest run tests/family_topbar.test.tsx tests/dashboard.test.tsx tests/assessment_sentence_flow.test.tsx tests/essay_reading_report_flow.test.tsx --environment jsdom
pnpm build
```

Expected: PASS and build succeeds.

- [ ] **Step 9: Review gate and commit**

Review:

```powershell
git diff -- apps/web/src/components/FamilyTopbar.tsx apps/web/src/app/children/[studentId]/page.tsx apps/web/src/app/children/[studentId]/essay/page.tsx apps/web/src/app/children/[studentId]/sentence/page.tsx apps/web/src/app/children/[studentId]/reading/page.tsx apps/web/src/app/parent/[studentId]/report/page.tsx apps/web/src/components/TaskCards.tsx apps/web/tests/dashboard.test.tsx apps/web/tests/assessment_sentence_flow.test.tsx apps/web/tests/essay_reading_report_flow.test.tsx apps/web/tests/family_topbar.test.tsx
```

Commit:

```powershell
git add apps/web/src/components/FamilyTopbar.tsx apps/web/src/app/children/[studentId]/page.tsx apps/web/src/app/children/[studentId]/essay/page.tsx apps/web/src/app/children/[studentId]/sentence/page.tsx apps/web/src/app/children/[studentId]/reading/page.tsx apps/web/src/app/parent/[studentId]/report/page.tsx apps/web/src/components/TaskCards.tsx apps/web/tests/dashboard.test.tsx apps/web/tests/assessment_sentence_flow.test.tsx apps/web/tests/essay_reading_report_flow.test.tsx apps/web/tests/family_topbar.test.tsx
git commit -m "feat: add family topbar and task navigation"
```

---

### Task 5: Polish Sentence Workshop Into A Complete Light Task

**Files:**
- Modify: `apps/web/src/app/children/[studentId]/sentence/page.tsx`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/tests/assessment_sentence_flow.test.tsx`

- [ ] **Step 1: Add failing sentence UI assertions**

In `apps/web/tests/assessment_sentence_flow.test.tsx`, update the sentence mock:

```tsx
  apiMocks.createSentenceTraining.mockResolvedValue({
    feedback: {
      encouragement: "你把画面写得更清楚了。",
      specific_improvement: "加入了可看见的细节",
      next_step: "再加一个动作，会更生动。",
      problem_monsters: ["空泛表达"],
    },
    settlement: {
      xp_delta: 25,
      level_after: 2,
      badge_code: "first_sentence_upgrade",
    },
  });
```

In `test("sentence page shows ai feedback and settlement", ...)`, add a pending response before rendering:

```tsx
  const sentenceResponse = {
    feedback: {
      encouragement: "你把画面写得更清楚了。",
      specific_improvement: "加入了可看见的细节",
      next_step: "再加一个动作，会更生动。",
      problem_monsters: ["空泛表达"],
    },
    settlement: {
      xp_delta: 25,
      level_after: 2,
      badge_code: "first_sentence_upgrade",
    },
  };
  let resolveSentenceTraining!: (value: typeof sentenceResponse) => void;
  const pendingSentenceTraining = new Promise<typeof sentenceResponse>((resolve) => {
    resolveSentenceTraining = resolve;
  });
  apiMocks.createSentenceTraining.mockReturnValueOnce(pendingSentenceTraining);
```

After clicking `提交给 AI 教练`, assert the loading state and resolve the pending response:

```tsx
  expect(screen.getByText("把一句话升级成小画面")).toBeInTheDocument();
  expect(screen.getByText("AI 教练正在看你的句子")).toBeInTheDocument();
  await act(async () => {
    resolveSentenceTraining(sentenceResponse);
    await pendingSentenceTraining;
  });
  expect(await screen.findByText("你把画面写得更清楚了。")).toBeInTheDocument();
  expect(screen.getByText("再加一个动作，会更生动。")).toBeInTheDocument();
  expect(screen.getByText("空泛表达")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "回到 Dashboard" })).toHaveAttribute("href", "/children/s1");
  expect(screen.getByRole("link", { name: "给家长看报告" })).toHaveAttribute("href", "/parent/s1/report");
```

In the failure test, replace expected alert text:

```tsx
    "这次句子练习没有提交成功。先别急，检查一下网络后再试一次。",
```

- [ ] **Step 2: Run sentence test and confirm it fails**

Run:

```powershell
cd apps/web
pnpm exec vitest run tests/assessment_sentence_flow.test.tsx --environment jsdom
```

Expected: FAIL because the page is still bare and the frontend type does not include `next_step` or `problem_monsters`.

- [ ] **Step 3: Expand sentence response type**

In `apps/web/src/lib/api.ts`, update `SentenceTrainingResponse`:

```ts
export type SentenceTrainingResponse = {
  feedback: {
    encouragement: string;
    specific_improvement: string;
    next_step: string;
    problem_monsters: string[];
  };
  settlement: Settlement;
};
```

- [ ] **Step 4: Replace sentence page UI**

In `apps/web/src/app/children/[studentId]/sentence/page.tsx`, add imports:

```tsx
import Link from "next/link";
import { Loader2, Sparkles } from "lucide-react";
```

Use this return body inside the existing `<main>`:

```tsx
      <div className="mx-auto max-w-4xl space-y-6">
        <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <Sparkles size={22} aria-hidden="true" className="text-[var(--wen-orange)]" />
            <h1 className="text-2xl font-bold">句子工坊</h1>
          </div>
          <p className="mt-2 text-[var(--wen-muted)]">把一句话升级成小画面</p>
          <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
            <label className="block font-semibold">
              原句
              <textarea
                className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                value={sourceSentence}
                onChange={(event) => setSourceSentence(event.target.value)}
                placeholder="例如：公园很美。"
              />
            </label>
            <label className="block font-semibold">
              升级后的句子
              <textarea
                className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                value={upgradedSentence}
                onChange={(event) => setUpgradedSentence(event.target.value)}
                placeholder="试着加一个动作、颜色、声音或比喻。"
              />
            </label>
            <button
              className="inline-flex items-center gap-2 rounded-lg bg-[var(--wen-leaf)] px-4 py-2 font-semibold text-white disabled:opacity-60"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? <Loader2 size={18} aria-hidden="true" className="animate-spin" /> : null}
              提交给 AI 教练
            </button>
          </form>
        </section>

        {isSubmitting ? (
          <p role="status" className="rounded-lg border border-[var(--wen-border)] bg-white p-4 font-semibold">
            AI 教练正在看你的句子
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="rounded-lg border border-[var(--wen-orange)] bg-white p-4 font-semibold">
            {error}
          </p>
        ) : null}
        {result ? (
          <>
            <section aria-label="AI 教练反馈" className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-bold">AI 教练反馈</h2>
              <p className="mt-3 font-semibold">{result.feedback.encouragement}</p>
              <p className="mt-3 text-[var(--wen-muted)]">{result.feedback.specific_improvement}</p>
              <h3 className="mt-5 font-semibold">发现的问题怪兽</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {result.feedback.problem_monsters.map((monster) => (
                  <span key={monster} className="rounded-lg bg-[var(--wen-bg)] px-3 py-2 font-semibold">
                    {monster}
                  </span>
                ))}
              </div>
              <h3 className="mt-5 font-semibold">下一小步</h3>
              <p className="mt-2">{result.feedback.next_step}</p>
            </section>
            <SettlementPanel settlement={result.settlement} />
            <nav aria-label="句子任务下一步" className="flex flex-wrap gap-3">
              <Link className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white" href={`/children/${studentId}`}>
                回到 Dashboard
              </Link>
              <Link className="rounded-lg border border-[var(--wen-border)] bg-white px-4 py-2 font-semibold" href={`/parent/${studentId}/report`}>
                给家长看报告
              </Link>
            </nav>
          </>
        ) : null}
      </div>
```

In the catch block, replace:

```tsx
      setError("提交失败，请稍后再试。");
```

with:

```tsx
      setError("这次句子练习没有提交成功。先别急，检查一下网络后再试一次。");
```

- [ ] **Step 5: Verify Task 5**

Run:

```powershell
cd apps/web
pnpm exec vitest run tests/assessment_sentence_flow.test.tsx --environment jsdom
pnpm build
```

Expected: PASS and build succeeds.

- [ ] **Step 6: Review gate and commit**

Review:

```powershell
git diff -- apps/web/src/app/children/[studentId]/sentence/page.tsx apps/web/src/lib/api.ts apps/web/tests/assessment_sentence_flow.test.tsx
```

Commit:

```powershell
git add apps/web/src/app/children/[studentId]/sentence/page.tsx apps/web/src/lib/api.ts apps/web/tests/assessment_sentence_flow.test.tsx
git commit -m "feat: polish sentence workshop task"
```

---

### Task 6: Add Friendly Construction States And Parent Navigation

**Files:**
- Create: `apps/web/src/components/ConstructionState.tsx`
- Modify: `apps/web/src/components/PlanetMap.tsx`
- Modify: `apps/web/src/app/children/[studentId]/page.tsx`
- Modify: `apps/web/src/app/children/[studentId]/reading/page.tsx`
- Modify: `apps/web/src/app/parent/[studentId]/report/page.tsx`
- Modify: `apps/web/tests/dashboard.test.tsx`
- Modify: `apps/web/tests/essay_reading_report_flow.test.tsx`

- [ ] **Step 1: Add failing construction and map-link tests**

In `apps/web/tests/dashboard.test.tsx`, add:

```tsx
  expect(screen.getByRole("link", { name: "阅读峡谷" })).toHaveAttribute(
    "href",
    "/children/s1/reading",
  );
```

In `apps/web/tests/essay_reading_report_flow.test.tsx`, replace the `reading page shows transfer tip` test with:

```tsx
test("reading page shows friendly construction state", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <ReadingPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  expect(await screen.findByRole("heading", { name: "阅读峡谷施工中" })).toBeInTheDocument();
  expect(screen.getByText("这里还在建设。小文星球会先把今天推荐的作文和句子任务陪你做好。")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "回到小文星球" })).toHaveAttribute("href", "/children/s1");
  expect(screen.getByRole("link", { name: "去完成今日推荐" })).toHaveAttribute("href", "/children/s1/sentence");
  expect(apiMocks.createReadingSession).not.toHaveBeenCalled();
});
```

In the report test, add:

```tsx
  expect(screen.getByRole("link", { name: "回到当前孩子 Dashboard" })).toHaveAttribute("href", "/children/s1");
```

- [ ] **Step 2: Run tests and confirm they fail**

Run:

```powershell
cd apps/web
pnpm exec vitest run tests/dashboard.test.tsx tests/essay_reading_report_flow.test.tsx --environment jsdom
```

Expected: FAIL because map links are `#`, the reading page is still a form, and report lacks an explicit dashboard action.

- [ ] **Step 3: Create ConstructionState component**

Create `apps/web/src/components/ConstructionState.tsx`:

```tsx
import Link from "next/link";

export function ConstructionState({
  title,
  body,
  primaryHref,
  secondaryHref,
}: {
  title: string;
  body: string;
  primaryHref: string;
  secondaryHref?: string;
}) {
  return (
    <section className="mx-auto max-w-3xl rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-bold">{title}</h1>
      <p className="mt-3 text-[var(--wen-muted)]">{body}</p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white" href={primaryHref}>
          回到小文星球
        </Link>
        {secondaryHref ? (
          <Link className="rounded-lg border border-[var(--wen-border)] px-4 py-2 font-semibold" href={secondaryHref}>
            去完成今日推荐
          </Link>
        ) : null}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Connect PlanetMap links**

In `apps/web/src/components/PlanetMap.tsx`, change the signature:

```tsx
export function PlanetMap({ studentId, places }: { studentId: string; places: string[] }) {
```

Add:

```tsx
  function hrefForPlace(place: string) {
    if (place.includes("句子")) {
      return `/children/${studentId}/sentence`;
    }
    if (place.includes("作文")) {
      return `/children/${studentId}/essay`;
    }
    return `/children/${studentId}/reading`;
  }
```

Replace:

```tsx
            href="#"
```

with:

```tsx
            href={hrefForPlace(place)}
```

In `apps/web/src/app/children/[studentId]/page.tsx`, update:

```tsx
        <PlanetMap studentId={studentId} places={dashboard.map} />
```

- [ ] **Step 5: Replace Reading page with construction state**

In `apps/web/src/app/children/[studentId]/reading/page.tsx`, remove form state and `createReadingSession` import. Keep `use(params)` and `FamilyTopbar`, then render:

```tsx
import { use } from "react";
import { ConstructionState } from "../../../../components/ConstructionState";
import { FamilyTopbar } from "../../../../components/FamilyTopbar";

export default function ReadingPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);

  return (
    <>
      <FamilyTopbar currentStudentId={studentId} />
      <main className="min-h-screen px-5 py-8 sm:px-8">
        <ConstructionState
          title="阅读峡谷施工中"
          body="这里还在建设。小文星球会先把今天推荐的作文和句子任务陪你做好。"
          primaryHref={`/children/${studentId}`}
          secondaryHref={`/children/${studentId}/sentence`}
        />
      </main>
    </>
  );
}
```

- [ ] **Step 6: Add explicit report navigation**

In `apps/web/src/app/parent/[studentId]/report/page.tsx`, import `Link`:

```tsx
import Link from "next/link";
```

Before closing the report `<section>`, add:

```tsx
        <div className="mt-6">
          <Link
            className="inline-flex rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white"
            href={`/children/${studentId}`}
          >
            回到当前孩子 Dashboard
          </Link>
        </div>
```

- [ ] **Step 7: Verify Task 6**

Run:

```powershell
cd apps/web
pnpm exec vitest run tests/dashboard.test.tsx tests/essay_reading_report_flow.test.tsx --environment jsdom
pnpm build
```

Expected: PASS and build succeeds.

- [ ] **Step 8: Review gate and commit**

Review:

```powershell
git diff -- apps/web/src/components/ConstructionState.tsx apps/web/src/components/PlanetMap.tsx apps/web/src/app/children/[studentId]/page.tsx apps/web/src/app/children/[studentId]/reading/page.tsx apps/web/src/app/parent/[studentId]/report/page.tsx apps/web/tests/dashboard.test.tsx apps/web/tests/essay_reading_report_flow.test.tsx
```

Commit:

```powershell
git add apps/web/src/components/ConstructionState.tsx apps/web/src/components/PlanetMap.tsx apps/web/src/app/children/[studentId]/page.tsx apps/web/src/app/children/[studentId]/reading/page.tsx apps/web/src/app/parent/[studentId]/report/page.tsx apps/web/tests/dashboard.test.tsx apps/web/tests/essay_reading_report_flow.test.tsx
git commit -m "feat: add construction states and report navigation"
```

---

### Task 7: Verify Four Child Profiles Differ In Dashboard, Recommendations, And Reports

**Files:**
- Modify: `apps/api/app/services/recommendations.py`
- Modify: `apps/api/app/services/reports.py`
- Modify: `apps/api/tests/test_auth_assessment_dashboard_api.py`
- Modify: `apps/api/tests/test_reading_report_api.py`

- [ ] **Step 1: Add failing four-profile dashboard test**

Append to `apps/api/tests/test_auth_assessment_dashboard_api.py`:

```python
from app.domain.models import Assessment


def test_four_demo_profiles_have_distinct_dashboard_shapes_and_recommendations(session, client):
    parent = seed_demo_data(session)
    students = sorted(parent_students(session, parent.id), key=lambda student: student.id)
    for student in students:
        session.add(
            Assessment(
                student_id=student.id,
                sentence_before="公园很美。",
                sentence_after="公园里的花红红的，风一吹就轻轻摇。",
                short_writing="我学会了骑车。刚开始我很害怕，后来爸爸扶着我练。",
                summary="完成入门小试炼，生成第一张能力草图。",
            )
        )
    session.commit()

    dashboards = {
        student.id: client.get(f"/api/students/{student.id}/dashboard").json()
        for student in students
    }

    ability_shapes = {
        tuple(dashboard["child_abilities"].values()) for dashboard in dashboards.values()
    }
    assert len(ability_shapes) == 4
    assert dashboards["s1"]["today_tasks"]["main"]["focus"] == "把细节写具体"
    assert dashboards["s2"]["today_tasks"]["quick"]["focus"] == "加动作或神态"
    assert dashboards["s3"]["today_tasks"]["main"]["focus"] == "把选材和结构说清楚"
    assert dashboards["s4"]["today_tasks"]["main"]["focus"] == "先把阅读内容概括清楚"
```

- [ ] **Step 2: Add failing report weak-point test**

Append to `apps/api/tests/test_reading_report_api.py`:

```python
def test_four_demo_profiles_report_weak_points_match_profile(session, client):
    parent = seed_demo_data(session)
    students = sorted(parent_students(session, parent.id), key=lambda student: student.id)

    reports = {
        student.id: client.post(
            f"/api/students/{student.id}/reports",
            json={"report_type": "stage"},
        ).json()["content"]
        for student in students
    }

    assert "继续保持细节和修改练习" in reports["s1"]["weak_points"]
    assert "表达还可以更具体" in reports["s2"]["weak_points"]
    assert "作文结构还需要更清晰" in reports["s3"]["weak_points"]
    assert "阅读概括可以继续练" in reports["s4"]["weak_points"]
```

- [ ] **Step 3: Run tests and confirm they fail**

Run:

```powershell
cd apps/api
uv run pytest tests/test_auth_assessment_dashboard_api.py tests/test_reading_report_api.py -q
```

Expected: FAIL because s4 recommendation and s2 report weak point do not yet match the profile.

- [ ] **Step 4: Update recommendation focus rules**

In `apps/api/app/services/recommendations.py`, replace the post-assessment focus logic:

```python
    essay_focus = "把选材和结构说清楚" if ability.structure < 40 else "把细节写具体"
    sentence_focus = "加动作或神态" if ability.observation < ability.expression else "加细节"
```

with:

```python
    if ability.summarization < 35 or ability.comprehension < 35:
        essay_focus = "先把阅读内容概括清楚"
    elif ability.structure < 40:
        essay_focus = "把选材和结构说清楚"
    else:
        essay_focus = "把细节写具体"

    sentence_focus = "加动作或神态" if ability.observation < ability.expression else "加细节"
```

- [ ] **Step 5: Update report weak-point rules**

In `apps/api/app/services/reports.py`, replace the weak point block:

```python
    weak_points = []
    if ability.structure < 45:
        weak_points.append("作文结构还需要更清晰")
    if ability.summarization < 45:
        weak_points.append("阅读概括可以继续练")
    if not weak_points:
        weak_points.append("继续保持细节和修改练习")
```

with:

```python
    weak_points = []
    if ability.expression < 35 or ability.observation < 35:
        weak_points.append("表达还可以更具体")
    if ability.structure < 45:
        weak_points.append("作文结构还需要更清晰")
    if ability.summarization < 45:
        weak_points.append("阅读概括可以继续练")
    if not weak_points:
        weak_points.append("继续保持细节和修改练习")
```

- [ ] **Step 6: Verify Task 7**

Run:

```powershell
cd apps/api
uv run pytest tests/test_auth_assessment_dashboard_api.py tests/test_reading_report_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Review gate and commit**

Review:

```powershell
git diff -- apps/api/app/services/recommendations.py apps/api/app/services/reports.py apps/api/tests/test_auth_assessment_dashboard_api.py apps/api/tests/test_reading_report_api.py
```

Commit:

```powershell
git add apps/api/app/services/recommendations.py apps/api/app/services/reports.py apps/api/tests/test_auth_assessment_dashboard_api.py apps/api/tests/test_reading_report_api.py
git commit -m "feat: validate demo profile differentiation"
```

---

### Task 8: Update No-Manual-URL E2E And Family-Test QA Records

**Files:**
- Modify: `apps/web/e2e/mvp.spec.ts`
- Create: `qa/2026-05-15-family-test-readiness-manual-qa.md`

- [ ] **Step 1: Update E2E to navigate through visible links**

Replace `apps/web/e2e/mvp.spec.ts` with:

```ts
import { expect, test } from "@playwright/test";

test.use({
  baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000",
});

test("family demo completes family-test readiness flow without manual URL edits", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "小文星球" })).toBeVisible();
  await page.getByRole("button", { name: "进入家庭内测" }).click();

  await expect(page.getByRole("link", { name: "小宇" })).toBeVisible();
  await expect(page.getByRole("link", { name: "小晴" })).toBeVisible();
  await expect(page.getByRole("link", { name: "小川" })).toBeVisible();
  await expect(page.getByRole("link", { name: "小禾" })).toBeVisible();
  await page.getByRole("link", { name: "小宇" }).click();

  await expect(page.getByRole("heading", { name: "小宇的小文星球" })).toBeVisible();
  await expect(page.getByText("当前孩子：小宇")).toBeVisible();
  await expect(page.getByRole("link", { name: "小晴" })).toHaveAttribute("href", "/children/s2");

  await page.getByRole("link", { name: /去写作文/ }).click();
  await page.getByLabel("作文题目").fill("我学会了骑车");
  await page
    .getByLabel("初稿")
    .fill("我学会了骑车。刚开始我很害怕。后来我会了。我很开心。");
  await page.getByRole("button", { name: "获得点评" }).click();
  await expect(page.getByText("给第二段加一个动作描写")).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "给第二段加一个动作描写" })).toBeChecked();
  await page
    .getByLabel("二稿")
    .fill("我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松开手后，我摇摇晃晃骑过花坛。");
  await page.getByRole("button", { name: "提交二稿" }).click();
  await expect(page.getByText("你把最重要的画面写清楚了。")).toBeVisible();
  await expect(page.getByText("完成 1 个修改任务")).toBeVisible();

  await page.getByRole("link", { name: "Dashboard" }).click();
  await page.getByRole("link", { name: /开始任务/ }).click();
  await page.getByLabel("原句").fill("公园很美。");
  await page
    .getByLabel("升级后的句子")
    .fill("清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。");
  await page.getByRole("button", { name: "提交给 AI 教练" }).click();
  await expect(page.getByText("加入了可看见的细节")).toBeVisible();
  await expect(page.getByText("+25 XP")).toBeVisible();

  await page.getByRole("link", { name: "给家长看报告" }).click();
  await expect(page.getByRole("heading", { name: "阶段报告" })).toBeVisible();
  await expect(page.getByText("完成了 1 个修改任务")).toBeVisible();
  await page.getByRole("link", { name: "回到当前孩子 Dashboard" }).click();

  await page.getByRole("link", { name: "阅读峡谷" }).click();
  await expect(page.getByRole("heading", { name: "阅读峡谷施工中" })).toBeVisible();
  await page.getByRole("link", { name: "回到小文星球" }).click();
  await expect(page.getByRole("heading", { name: "小宇的小文星球" })).toBeVisible();
});
```

- [ ] **Step 2: Run full automated verification**

Run:

```powershell
cd apps/api
uv run pytest -q
cd ../web
pnpm test
pnpm build
pnpm e2e
```

Expected:

- Backend tests pass.
- Frontend unit tests pass.
- Production build succeeds.
- Playwright E2E passes and does not use `page.goto(...)` after the initial family entry.

- [ ] **Step 3: Run four-profile manual QA**

Start local apps with mock provider:

```powershell
cd apps/api
uv run uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd apps/web
pnpm dev
```

Open `http://localhost:3000` and verify:

```text
进入家庭内测
-> 小宇 Dashboard: ability bars, recommendation focus, parent report weak points
-> switch to 小晴: ability bars, recommendation focus, parent report weak points
-> switch to 小川: ability bars, recommendation focus, parent report weak points
-> switch to 小禾: ability bars, recommendation focus, parent report weak points
```

- [ ] **Step 4: Run real LLM QA for 小宇 essay and sentence**

Use local `.env` with these variables set to the real provider credentials supplied outside git:

```text
LLM_PROVIDER=http
LLM_PROMPT_VERSION=v0.2-quality-spine-2026-05-14
LLM_API_KEY
LLM_MODEL
LLM_BASE_URL
LLM_DAILY_LIMIT_ENABLED=false
```

Run:

```text
进入家庭内测
-> 小宇
-> 去写作文
-> title: 我学会了骑车
-> draft: 我学会了骑车。刚开始我很害怕。后来我会了。我很开心。
-> 获得点评
-> confirm one default-selected revision task
-> revision: 我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松手后，我摇摇晃晃骑过花坛。我开心得跳了起来。
-> 提交二稿
-> 回到 Dashboard
-> 句子工坊
-> source sentence: 公园很美。
-> upgraded sentence: 清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。
-> 提交给 AI 教练
-> 家长报告
```

- [ ] **Step 5: Create filled QA record**

Create `qa/2026-05-15-family-test-readiness-manual-qa.md` only after the manual run is complete. The file must include:

- `# WenLingo Family Test Readiness Manual QA`
- `日期：2026-05-15`
- `执行人：Codex`
- `环境：local browser, FastAPI localhost:8000, Next.js localhost:3000`
- A `## 四画像验证` table with rows for 小宇, 小晴, 小川, and 小禾. Each row must contain the ability values seen in browser, the recommendation focus text seen in browser, the report weak point text seen in browser, and the pass/fail result for that child.
- A `## 小宇 Real LLM Essay QA` section with the provider, model, prompt version, returned revision task count, anti-ghostwriting verdict with evidence, comparison evidence, retry status, and fallback status from the run.
- A `## 小宇 Real LLM Sentence QA` section with the provider, model, prompt version, encouragement verdict with evidence, concrete-improvement verdict with evidence, anti-rewrite verdict with evidence, retry status, and fallback status from the run.
- A `## Navigation QA` section with verdicts for no manual URL editing after family entry, child switcher routing, dashboard task-card entry, and Reading Canyon construction-state next action.
- A `## Verdict` section with one of these values: `pass`, `pass with follow-up`, or `fail`, plus one sentence explaining the result.

Before committing, read the QA file once and confirm every field contains an observed value from the run.

- [ ] **Step 6: Verify `.env` remains untracked and commit**

Run:

```powershell
git status --short
```

Expected: `.env` is not staged. If `.env` appears as untracked, leave it unstaged.

Commit:

```powershell
git add apps/web/e2e/mvp.spec.ts qa/2026-05-15-family-test-readiness-manual-qa.md
git commit -m "test: verify family test readiness flow"
```

---

## Final Verification

After Task 8, run:

```powershell
cd apps/api
uv run pytest -q
cd ../web
pnpm test
pnpm build
pnpm e2e
```

Expected:

- Backend tests pass.
- Frontend unit tests pass.
- Production build succeeds.
- Playwright E2E passes.
- `qa/2026-05-15-family-test-readiness-manual-qa.md` contains concrete four-profile observations and real LLM observations for 小宇 essay and sentence flows.

## Completion Definition

The implementation is complete when:

1. A normal family tester can navigate from family entry through child selection, Dashboard, Essay Castle, Sentence Workshop, Parent Report, and Reading Canyon construction state without manual URL editing.
2. The global topbar shows `小文星球`, the current child, switcher links for the four seeded profiles, and links to Dashboard, Essay Castle, Sentence Workshop, and Parent Report.
3. Dashboard task cards enter both essay and sentence tasks, and task card titles do not duplicate category labels.
4. Essay feedback prompts real providers toward one minimal revision task, revision checkboxes default selected, and settlement/report evidence reflect completed task count.
5. Sentence Workshop uses provider DI, shared schema validation, retry/fallback, `LLMCallLog` traceability, and a polished child-friendly UI with clear next actions.
6. `LLMCallLog.student_id` and `LLMCallLog.task_name` are recorded for essay and sentence student workflow calls.
7. Daily real-provider LLM usage protection can be enabled by env config, applies by `student_id + task_name`, and stays disabled by default.
8. Reading Canyon and unfinished planned modules show warm construction states with a useful next action.
9. The four demo child profiles differ in Dashboard ability shapes, recommendation focus, and parent report weak points.
10. Automated backend, frontend, and E2E tests cover the main acceptance points.
11. Manual QA records verify the four child profiles and real LLM 小宇 essay/sentence quality, including retry/fallback observations.
