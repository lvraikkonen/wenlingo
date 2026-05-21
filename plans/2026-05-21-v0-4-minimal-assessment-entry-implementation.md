# WenLingo V0.4 Minimal Assessment Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the V0.4 entry assessment so a new/default child completes one fixed sentence upgrade plus one short writing task, receives a first ability sketch, and returns to a personalized dashboard recommendation.

**Architecture:** Keep the HTTP route thin and move ordered assessment orchestration into a backend service that reuses the existing sentence and essay LLM task wrappers in one database transaction. Persist assessment artifact links directly on `Assessment`, keep ability history source-linked to `SentenceTraining` and `EssayVersion`, and treat assessment-created essays as completed assessment artifacts outside the normal Essay Castle revision flow. Replace the current bare assessment form with a four-step client flow and a lightweight inline SVG radar sketch.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy, Alembic, Pydantic, pytest, Next.js App Router, React 19, TypeScript, Vitest, Playwright, Tailwind CSS, lucide-react.

---

## Source Documents

- Approved V0.4 design spec: `specs/2026-05-21-v0.4-minimal-assessment-entry-design.md`
- V0.4 handoff: `specs/2026-05-21-wenlingo-v0.4-minimal-assessment-handoff.md`
- V0.3 review: `reviews/2026-05-21-v0.3-ability-flywheel-gstack-review.md`
- Project agent rules: `AGENT.md`
- Current V0.3 plan for local conventions: `plans/2026-05-19-v0-3-ability-flywheel-foundation-implementation.md`

## Execution Rules

- Store this Superpowers-generated plan in `plans/` because `AGENT.md` overrides the skill default path.
- Run tasks in order and commit after each task's verification command passes.
- Use TDD for behavior changes: failing test first, focused failing command, minimal implementation, focused passing command.
- Keep the four seeded demo children behavior stable unless a task explicitly updates only test expectations for the new assessment response.
- Do not add a reading diagnostic, material question flow, outline-generation flow, new LLM task type, charting dependency, parent assessment report, retake UI, or changes to the four seeded demo ability profiles.
- Use `SentenceFocus.detail.value` after verifying the enum member name in `apps/api/app/domain/enums.py`; do not hard-code `"加细节"` inside backend orchestration.
- Keep the frontend radar chart inline SVG/CSS only.
- On Windows, use `corepack pnpm ...` when `pnpm` is not on `PATH`.

## Scope Check

The spec is one vertical slice: docs preflight, persistence shape, assessment orchestration, response contract, dashboard transition, frontend assessment flow, tests, E2E, and manual QA notes. It does not need separate subsystem plans because each task below produces working, testable software while staying inside the same V0.4 entry-assessment path.

## File Structure Map

- Create: `qa/2026-05-21-v0.3-release-note.md` - concise V0.3 release note before V0.4 coding starts.
- Create: `qa/2026-05-21-stale-sqlite-cleanup.md` - local stale SQLite cleanup runbook for API/manual/Playwright databases.
- Modify: `README.md` - link the stale SQLite cleanup runbook from the existing Playwright verification note.
- Modify: `apps/api/app/domain/models.py` - add nullable artifact references to `Assessment`.
- Create: `apps/api/app/db/migrations/versions/20260521_assessment_artifacts.py` - add assessment artifact columns, indexes, and foreign keys.
- Modify: `apps/api/tests/test_domain_models.py` - assert assessment artifact reference columns are nullable and indexed.
- Modify: `apps/api/tests/test_migrations.py` - assert migration text contains the new columns, indexes, foreign keys, and down revision.
- Create: `apps/api/app/services/essay_workflow.py` - move deterministic essay status and ability-delta helpers into a shared service module.
- Create: `apps/api/app/services/assessment.py` - orchestrate the full entry assessment in one transaction boundary owned by the route.
- Modify: `apps/api/app/api/routes/assessment.py` - validate request lengths, load dependencies, call the service, rollback on failures, commit once, and return the additive response.
- Modify: `apps/api/app/api/routes/essays.py` - import shared essay helpers and reject assessment-only essays from revision.
- Create: `apps/api/tests/test_assessment_api.py` - cover artifact creation, ability history, fallback, rollback, 422s, and assessment-only essay exclusion.
- Modify: `apps/api/tests/test_auth_assessment_dashboard_api.py` - update the assessment/dashboard test to expect artifact links, ability history, ability sketch, and `settlement`.
- Modify: `apps/api/tests/test_essay_workflow_api.py` - import moved essay helper functions from `app.services.essay_workflow`.
- Modify: `apps/web/src/lib/api.ts` - expand `AssessmentResponse` for artifact IDs, ability sketch, and settlement.
- Modify: `apps/web/src/app/children/[studentId]/assessment/page.tsx` - replace the bare form with the four-step child flow and inline radar sketch.
- Modify: `apps/web/tests/api.test.ts` - assert the API client accepts the additive assessment response.
- Modify: `apps/web/tests/assessment_sentence_flow.test.tsx` - cover assessment steps, fixed source sentence, one submission, loading, retry, radar labels, and no chart package.
- Modify: `apps/web/e2e/mvp.spec.ts` - add an entry-assessment E2E for a default child inserted into the Playwright SQLite database and keep the existing MVP demo flow.
- Create: `qa/2026-05-21-v0.4-minimal-assessment-manual-qa.md` - manual QA checklist and timing notes.

---

### Task 1: Close V0.3 Release Docs And SQLite Cleanup Runbook

**Files:**
- Create: `qa/2026-05-21-v0.3-release-note.md`
- Create: `qa/2026-05-21-stale-sqlite-cleanup.md`
- Modify: `README.md`

- [ ] **Step 1: Create the V0.3 release note**

Create `qa/2026-05-21-v0.3-release-note.md`:

```markdown
# WenLingo V0.3 Ability Flywheel Release Note

Date: 2026-05-21
Status: Released for V0.4 base

## Summary

V0.3 established the ability flywheel foundation. Sentence training, essay first drafts, and essay revisions now produce source-linked `AbilityHistory` rows, and dashboard recommendations are driven by the current `AbilityProfile` instead of static assessment copy.

## Shipped Behavior

- `AbilityHistory` records old value, new value, delta, source type, source id, and creation time.
- Sentence training applies canonical LLM ability deltas, with `{ "expression": 2, "observation": 2 }` fallback when the provider returns only non-canonical positive keys.
- Essay first-draft feedback applies deterministic expression/structure deltas linked to the first `EssayVersion`.
- Essay revision comparison applies deterministic revision deltas linked to the revision `EssayVersion`.
- Dashboard recommendations use all-default ability detection for the assessment entry recommendation.
- The four seeded demo children retain distinct dashboard shapes and recommendations.
- LLM payloads wrap student text in XML-like tags and log provider, prompt, raw response, retry, and validation metadata.

## Verification Record

- Backend V0.3 focused tests passed during the V0.3 implementation cycle.
- Manual QA notes are recorded in `qa/2026-05-21-v0.3-ability-flywheel-manual-qa.md`.
- GStack review is recorded in `reviews/2026-05-21-v0.3-ability-flywheel-gstack-review.md`.

## Known Follow-Up

V0.4 will turn the all-default new-child state into a real entry assessment that creates sentence, essay, assessment, ability-history, and settlement artifacts in one transaction.
```

- [ ] **Step 2: Create the stale SQLite cleanup runbook**

Create `qa/2026-05-21-stale-sqlite-cleanup.md`:

```markdown
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
```

- [ ] **Step 3: Link the cleanup runbook from `README.md`**

In `README.md`, replace this sentence in the Verification section:

```markdown
uses a local SQLite file at `apps/api/playwright-e2e.db`; set
`PLAYWRIGHT_DATABASE_URL` to point it at another database. Use
`corepack pnpm e2e -- mvp.spec.ts` on Windows if `pnpm` is not on PATH.
```

with:

```markdown
uses a local SQLite file at `apps/api/playwright-e2e.db`; set
`PLAYWRIGHT_DATABASE_URL` to point it at another database. Remove stale SQLite
files before E2E runs using `qa/2026-05-21-stale-sqlite-cleanup.md`. Use
`corepack pnpm e2e -- mvp.spec.ts` on Windows if `pnpm` is not on PATH.
```

- [ ] **Step 4: Verify docs are present**

Run:

```bash
git diff -- qa/2026-05-21-v0.3-release-note.md qa/2026-05-21-stale-sqlite-cleanup.md README.md
```

Expected: diff shows both new QA docs and the README Verification link.

- [ ] **Step 5: Commit**

```bash
git add qa/2026-05-21-v0.3-release-note.md qa/2026-05-21-stale-sqlite-cleanup.md README.md
git commit -m "docs: close v0.3 release preflight"
```

---

### Task 2: Add Assessment Artifact References To Model And Migration

**Files:**
- Modify: `apps/api/app/domain/models.py`
- Create: `apps/api/app/db/migrations/versions/20260521_assessment_artifacts.py`
- Modify: `apps/api/tests/test_domain_models.py`
- Modify: `apps/api/tests/test_migrations.py`

- [ ] **Step 1: Write failing model tests**

In `apps/api/tests/test_domain_models.py`, append:

```python
def test_assessment_artifact_references_are_nullable_and_indexed():
    sentence_column = Assessment.__table__.c["sentence_training_id"]
    essay_column = Assessment.__table__.c["essay_id"]
    index_columns = {
        column.name
        for index in Assessment.__table__.indexes
        for column in index.columns
    }

    assert sentence_column.nullable is True
    assert essay_column.nullable is True
    assert sentence_column.foreign_keys
    assert essay_column.foreign_keys
    assert "sentence_training_id" in index_columns
    assert "essay_id" in index_columns
```

- [ ] **Step 2: Write failing migration test**

In `apps/api/tests/test_migrations.py`, append:

```python
def test_assessment_artifact_references_have_migration():
    migration_path = Path("app/db/migrations/versions/20260521_assessment_artifacts.py")
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "20260521_assessment_artifacts" in migration_text
    assert 'down_revision = "20260520_ability_history"' in migration_text
    assert "assessment" in migration_text
    assert "sentence_training_id" in migration_text
    assert "essay_id" in migration_text
    assert "ix_assessment_sentence_training_id" in migration_text
    assert "ix_assessment_essay_id" in migration_text
    assert "fk_assessment_sentence_training_id_sentencetraining" in migration_text
    assert "fk_assessment_essay_id_essay" in migration_text
```

- [ ] **Step 3: Run focused tests and confirm they fail**

Run:

```bash
cd apps/api
uv run pytest tests/test_domain_models.py::test_assessment_artifact_references_are_nullable_and_indexed tests/test_migrations.py::test_assessment_artifact_references_have_migration -q
```

Expected: FAIL because `Assessment.sentence_training_id`, `Assessment.essay_id`, and the migration file do not exist.

- [ ] **Step 4: Add model fields**

In `apps/api/app/domain/models.py`, replace the `Assessment` class with:

```python
class Assessment(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    sentence_before: str
    sentence_after: str
    short_writing: str
    summary: str
    sentence_training_id: str | None = Field(
        default=None,
        foreign_key="sentencetraining.id",
        index=True,
    )
    essay_id: str | None = Field(default=None, foreign_key="essay.id", index=True)
    created_at: datetime = timestamp_field()
```

- [ ] **Step 5: Add migration**

Create `apps/api/app/db/migrations/versions/20260521_assessment_artifacts.py`:

```python
"""Add assessment artifact references."""

import sqlalchemy as sa
from alembic import op


revision = "20260521_assessment_artifacts"
down_revision = "20260520_ability_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assessment", sa.Column("sentence_training_id", sa.String(), nullable=True))
    op.add_column("assessment", sa.Column("essay_id", sa.String(), nullable=True))
    op.create_index(
        "ix_assessment_sentence_training_id",
        "assessment",
        ["sentence_training_id"],
        unique=False,
    )
    op.create_index("ix_assessment_essay_id", "assessment", ["essay_id"], unique=False)
    op.create_foreign_key(
        "fk_assessment_sentence_training_id_sentencetraining",
        "assessment",
        "sentencetraining",
        ["sentence_training_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_assessment_essay_id_essay",
        "assessment",
        "essay",
        ["essay_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_assessment_essay_id_essay",
        "assessment",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_assessment_sentence_training_id_sentencetraining",
        "assessment",
        type_="foreignkey",
    )
    op.drop_index("ix_assessment_essay_id", table_name="assessment")
    op.drop_index("ix_assessment_sentence_training_id", table_name="assessment")
    op.drop_column("assessment", "essay_id")
    op.drop_column("assessment", "sentence_training_id")
```

- [ ] **Step 6: Run focused tests and confirm they pass**

Run:

```bash
cd apps/api
uv run pytest tests/test_domain_models.py::test_assessment_artifact_references_are_nullable_and_indexed tests/test_migrations.py::test_assessment_artifact_references_have_migration -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/domain/models.py apps/api/app/db/migrations/versions/20260521_assessment_artifacts.py apps/api/tests/test_domain_models.py apps/api/tests/test_migrations.py
git commit -m "feat: link assessments to created artifacts"
```

---

### Task 3: Add Backend Assessment Behavior Tests

**Files:**
- Create: `apps/api/tests/test_assessment_api.py`
- Modify: `apps/api/tests/test_auth_assessment_dashboard_api.py`

- [ ] **Step 1: Create the assessment API test file**

Create `apps/api/tests/test_assessment_api.py`:

```python
import json

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_db_session, get_llm_provider
from app.domain.enums import TaskType
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    Assessment,
    Essay,
    EssayVersion,
    GameEvent,
    LLMCallLog,
    ParentUser,
    SentenceTraining,
    StudentProfile,
)
from app.main import create_app
from app.services.essay_workflow import ASSESSMENT_ESSAY_STATUS
from app.services.llm_provider import LLMProviderResponse, MockLLMProvider


def create_default_child(session) -> StudentProfile:
    parent = ParentUser(email="v04-parent@example.com", display_name="V0.4 Parent")
    student = StudentProfile(
        parent_id=parent.id,
        name="小新",
        persona="real_child",
        is_real_child=True,
    )
    ability = AbilityProfile(student_id=student.id)
    session.add(parent)
    session.add(student)
    session.add(ability)
    session.commit()
    return student


def valid_assessment_payload() -> dict[str, str]:
    return {
        "sentence_before": "公园很美。",
        "sentence_after": "公园里的花红红的，风一吹就轻轻摇。",
        "short_writing": "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
    }


class AlwaysInvalidAssessmentProvider:
    provider_name = "fake"
    model_name = "assessment-invalid"

    async def complete_json(self, task_name, payload):
        parsed = {"bad": "shape"}
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


def test_assessment_creates_artifacts_history_settlement_and_dashboard_transition(session, client):
    student = create_default_child(session)
    before_dashboard = client.get(f"/api/students/{student.id}/dashboard").json()

    response = client.post(
        f"/api/students/{student.id}/assessment",
        json=valid_assessment_payload(),
    )

    assert before_dashboard["today_tasks"]["main"]["kind"] == "assessment"
    assert response.status_code == 201
    payload = response.json()
    assert payload["assessment"]["summary"] == "完成入门小试炼，生成第一张能力草图。"
    assert payload["assessment"]["sentence_training_id"]
    assert payload["assessment"]["essay_id"]
    assert payload["ability_sketch"] == {
        "reading_power": 40,
        "specific_writing_power": 46,
        "revision_power": 40,
    }
    assert payload["settlement"]["xp_delta"] == 20
    assert payload["game_event"]["xp_delta"] == 20

    training = session.get(SentenceTraining, payload["assessment"]["sentence_training_id"])
    essay = session.get(Essay, payload["assessment"]["essay_id"])
    assessment = session.exec(select(Assessment)).one()
    first_draft = session.exec(
        select(EssayVersion).where(EssayVersion.essay_id == essay.id)
    ).one()
    event = session.exec(select(GameEvent)).one()
    history = session.exec(select(AbilityHistory)).all()
    ability = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).one()
    post_dashboard = client.get(f"/api/students/{student.id}/dashboard").json()

    assert training.source_sentence == "公园很美。"
    assert training.upgraded_sentence == "公园里的花红红的，风一吹就轻轻摇。"
    assert training.focus == "加细节"
    assert essay.status == ASSESSMENT_ESSAY_STATUS
    assert essay.title == "入门小写作"
    assert first_draft.version_label == "first_draft"
    assert first_draft.content == valid_assessment_payload()["short_writing"]
    assert assessment.sentence_training_id == training.id
    assert assessment.essay_id == essay.id
    assert event.task_type == TaskType.assessment
    assert event.evidence["sentence_training_id"] == training.id
    assert event.evidence["essay_id"] == essay.id
    assert ability.expression == 49
    assert ability.observation == 44
    assert ability.structure == 45
    assert ability.revision == 40
    assert {(row.ability_name, row.delta, row.source_type, row.source_id) for row in history} == {
        ("expression", 4, TaskType.sentence, training.id),
        ("observation", 4, TaskType.sentence, training.id),
        ("expression", 5, TaskType.essay, first_draft.id),
        ("structure", 5, TaskType.essay, first_draft.id),
    }
    assert all(row.source_type != TaskType.assessment for row in history)
    assert post_dashboard["ability_note"] == "第一张能力草图"
    assert post_dashboard["today_tasks"]["main"]["kind"] != "assessment"


def test_schema_valid_fallback_can_complete_assessment(session):
    student = create_default_child(session)
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_llm_provider] = lambda: AlwaysInvalidAssessmentProvider()

    with TestClient(app) as test_client:
        response = test_client.post(
            f"/api/students/{student.id}/assessment",
            json=valid_assessment_payload(),
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert session.exec(select(Assessment)).one().sentence_training_id
    assert session.exec(select(EssayVersion)).one().llm_call_log_id is not None
    logs = session.exec(select(LLMCallLog)).all()
    assert {log.task_name for log in logs} == {"sentence_upgrade_feedback", "essay_feedback"}
    assert all(log.validation_ok is False for log in logs)
    assert response.json()["ability_sketch"]["specific_writing_power"] > 40


def test_ghostwriting_rolls_back_all_partial_assessment_rows(session, client):
    student = create_default_child(session)

    response = client.post(
        f"/api/students/{student.id}/assessment",
        json={
            "sentence_before": "公园很美。",
            "sentence_after": "公园里的花在风里轻轻摇。",
            "short_writing": "请帮我写作文。我想直接生成一篇完整作文，不想自己写。",
        },
    )

    assert response.status_code == 400
    assert "不能替你写完整作文" in response.json()["detail"]
    assert session.exec(select(Assessment)).all() == []
    assert session.exec(select(SentenceTraining)).all() == []
    assert session.exec(select(Essay)).all() == []
    assert session.exec(select(EssayVersion)).all() == []
    assert session.exec(select(AbilityHistory)).all() == []
    assert session.exec(select(GameEvent)).all() == []
    assert session.exec(select(LLMCallLog)).all() == []


def test_unhandled_assessment_error_rolls_back_partial_rows(session, monkeypatch):
    async def raising_essay_feedback(*args, **kwargs):
        raise RuntimeError("essay pipeline exploded")

    student = create_default_child(session)
    monkeypatch.setattr("app.services.assessment.essay_feedback", raising_essay_feedback)
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider()

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            f"/api/students/{student.id}/assessment",
            json=valid_assessment_payload(),
        )
    app.dependency_overrides.clear()

    assert response.status_code == 500
    assert session.exec(select(Assessment)).all() == []
    assert session.exec(select(SentenceTraining)).all() == []
    assert session.exec(select(Essay)).all() == []
    assert session.exec(select(EssayVersion)).all() == []
    assert session.exec(select(AbilityHistory)).all() == []
    assert session.exec(select(GameEvent)).all() == []
    assert session.exec(select(LLMCallLog)).all() == []


def test_assessment_rejects_overlong_sentence_and_writing_inputs(session, client):
    student = create_default_child(session)

    sentence_response = client.post(
        f"/api/students/{student.id}/assessment",
        json={
            "sentence_before": "细" * 501,
            "sentence_after": "公园里的花在风里轻轻摇。",
            "short_writing": valid_assessment_payload()["short_writing"],
        },
    )
    writing_response = client.post(
        f"/api/students/{student.id}/assessment",
        json={
            "sentence_before": "公园很美。",
            "sentence_after": "公园里的花在风里轻轻摇。",
            "short_writing": "文" * 501,
        },
    )

    assert sentence_response.status_code == 422
    assert writing_response.status_code == 422
    assert session.exec(select(Assessment)).all() == []


def test_assessment_created_essay_is_not_revisable(session, client):
    student = create_default_child(session)
    created = client.post(
        f"/api/students/{student.id}/assessment",
        json=valid_assessment_payload(),
    )
    essay_id = created.json()["assessment"]["essay_id"]

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json={
            "content": "我学会了骑车。后来我能慢慢骑过小路，还听见爸爸在后面给我鼓掌。"
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "essay not found"
    assert len(session.exec(select(EssayVersion)).all()) == 1
    assert len(session.exec(select(GameEvent)).all()) == 1
```

- [ ] **Step 2: Update the existing auth/dashboard assessment test**

In `apps/api/tests/test_auth_assessment_dashboard_api.py`, update imports:

```python
from app.domain.enums import TaskType
from app.domain.models import (
    AbilityHistory,
    Assessment,
    Essay,
    EssayVersion,
    SentenceTraining,
    StudentProfile,
)
from app.services.essay_workflow import ASSESSMENT_ESSAY_STATUS
```

Replace `test_assessment_creates_first_ability_sketch_and_dashboard` with:

```python
def test_assessment_creates_first_ability_sketch_and_dashboard(session, client):
    parent = seed_demo_data(session)
    student_id = parent_students(session, parent.id)[0].id

    response = client.post(
        f"/api/students/{student_id}/assessment",
        json={
            "sentence_before": "公园很美。",
            "sentence_after": "公园里的花红红的，风一吹就轻轻摇。",
            "short_writing": "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["assessment"]["summary"] == "完成入门小试炼，生成第一张能力草图。"
    assert payload["assessment"]["sentence_training_id"]
    assert payload["assessment"]["essay_id"]
    assert set(payload["ability_sketch"]) == {
        "reading_power",
        "specific_writing_power",
        "revision_power",
    }
    assert payload["settlement"]["xp_delta"] == 20
    assert payload["game_event"]["xp_delta"] == 20

    assessment = session.exec(select(Assessment)).one()
    training = session.get(SentenceTraining, payload["assessment"]["sentence_training_id"])
    essay = session.get(Essay, payload["assessment"]["essay_id"])
    version = session.exec(
        select(EssayVersion).where(EssayVersion.essay_id == essay.id)
    ).one()
    history = session.exec(select(AbilityHistory)).all()

    assert assessment.sentence_training_id == training.id
    assert assessment.essay_id == essay.id
    assert essay.status == ASSESSMENT_ESSAY_STATUS
    assert {(row.source_type, row.source_id) for row in history} == {
        (TaskType.sentence, training.id),
        (TaskType.essay, version.id),
    }
    dashboard = client.get(f"/api/students/{student_id}/dashboard").json()
    assert dashboard["ability_note"] == "第一张能力草图"
    assert dashboard["today_tasks"]["main"]["kind"] in {"essay", "sentence"}
    assert set(dashboard["child_abilities"].keys()) == {
        "reading_power",
        "specific_writing_power",
        "revision_power",
    }
```

- [ ] **Step 3: Run focused tests and confirm they fail**

Run:

```bash
cd apps/api
uv run pytest tests/test_assessment_api.py tests/test_auth_assessment_dashboard_api.py::test_assessment_creates_first_ability_sketch_and_dashboard -q
```

Expected: FAIL because `app.services.assessment`, `app.services.essay_workflow`, artifact response fields, and assessment-created artifacts do not exist yet.

- [ ] **Step 4: Commit the failing tests**

```bash
git add apps/api/tests/test_assessment_api.py apps/api/tests/test_auth_assessment_dashboard_api.py
git commit -m "test: define v0.4 assessment backend behavior"
```

---

### Task 4: Implement Assessment Service And Thin Route

**Files:**
- Create: `apps/api/app/services/essay_workflow.py`
- Create: `apps/api/app/services/assessment.py`
- Modify: `apps/api/app/api/routes/assessment.py`
- Modify: `apps/api/app/api/routes/essays.py`
- Modify: `apps/api/tests/test_essay_workflow_api.py`

- [ ] **Step 1: Move shared essay workflow helpers**

Create `apps/api/app/services/essay_workflow.py`:

```python
ASSESSMENT_ESSAY_STATUS = "assessment_completed"
REVISION_REQUESTED_STATUS = "revision_requested"
SETTLED_ESSAY_STATUS = "settled"


def draft_ability_deltas(improvement_count: int) -> dict[str, int]:
    delta = 3 if improvement_count == 3 else 5
    return {"expression": delta, "structure": delta}


def revision_ability_deltas(evidence_count: int) -> dict[str, int]:
    return {"revision": 5 if evidence_count >= 2 else 4}
```

In `apps/api/app/api/routes/essays.py`, remove the local `draft_ability_deltas` and `revision_ability_deltas` definitions and add:

```python
from app.services.essay_workflow import (
    ASSESSMENT_ESSAY_STATUS,
    REVISION_REQUESTED_STATUS,
    SETTLED_ESSAY_STATUS,
    draft_ability_deltas,
    revision_ability_deltas,
)
```

Then replace:

```python
essay = Essay(student_id=student_id, title=request.title, status="revision_requested")
```

with:

```python
essay = Essay(student_id=student_id, title=request.title, status=REVISION_REQUESTED_STATUS)
```

and replace:

```python
if essay.status == "settled":
    raise HTTPException(status_code=409, detail="essay already settled")
```

with:

```python
if essay.status == ASSESSMENT_ESSAY_STATUS:
    raise HTTPException(status_code=404, detail="essay not found")
if essay.status == SETTLED_ESSAY_STATUS:
    raise HTTPException(status_code=409, detail="essay already settled")
```

and replace:

```python
essay.status = "settled"
```

with:

```python
essay.status = SETTLED_ESSAY_STATUS
```

In `apps/api/tests/test_essay_workflow_api.py`, replace:

```python
from app.api.routes.essays import EssayRevisionCreate, draft_ability_deltas, submit_revision
```

with:

```python
from app.api.routes.essays import EssayRevisionCreate, submit_revision
from app.services.essay_workflow import draft_ability_deltas
```

- [ ] **Step 2: Add the assessment service**

Create `apps/api/app/services/assessment.py`:

```python
from dataclasses import dataclass

from sqlmodel import Session

from app.core.config import Settings
from app.domain.enums import SentenceFocus, TaskType
from app.domain.models import (
    AbilityProfile,
    Assessment,
    Essay,
    EssayVersion,
    GameEvent,
    SentenceTraining,
    StudentProfile,
)
from app.services.abilities import VALID_ABILITY_NAMES, apply_ability_delta, to_child_abilities
from app.services.ai_tasks import essay_feedback, sentence_upgrade_feedback
from app.services.essay_workflow import ASSESSMENT_ESSAY_STATUS, draft_ability_deltas
from app.services.gamification import settle_task
from app.services.llm_provider import LLMProvider


ASSESSMENT_SUMMARY = "完成入门小试炼，生成第一张能力草图。"
ASSESSMENT_ESSAY_TITLE = "入门小写作"
SENTENCE_ABILITY_DELTA_FALLBACK = {"expression": 2, "observation": 2}


@dataclass(frozen=True)
class EntryAssessmentResult:
    assessment: Assessment
    sentence_training: SentenceTraining
    essay: Essay
    first_draft: EssayVersion
    ability_sketch: dict[str, int]
    settlement: GameEvent


def sentence_assessment_deltas(raw_deltas: dict[str, int]) -> dict[str, int]:
    if any(
        ability_name in VALID_ABILITY_NAMES and raw_delta > 0
        for ability_name, raw_delta in raw_deltas.items()
    ):
        return raw_deltas
    return SENTENCE_ABILITY_DELTA_FALLBACK


async def complete_entry_assessment(
    *,
    session: Session,
    student: StudentProfile,
    ability: AbilityProfile,
    provider: LLMProvider,
    settings: Settings,
    sentence_before: str,
    sentence_after: str,
    short_writing: str,
) -> EntryAssessmentResult:
    focus = SentenceFocus.detail.value
    sentence_result = await sentence_upgrade_feedback(
        provider=provider,
        source_sentence=sentence_before,
        upgraded_sentence=sentence_after,
        focus=focus,
        session=session,
        prompt_version=settings.llm_prompt_version,
        student_id=student.id,
        daily_limit_enabled=settings.llm_daily_limit_enabled,
        daily_limit_per_student_task=settings.llm_daily_limit_per_student_task,
    )
    sentence_feedback = sentence_result.output
    training = SentenceTraining(
        student_id=student.id,
        source_sentence=sentence_before,
        upgraded_sentence=sentence_after,
        focus=focus,
        ai_feedback=sentence_feedback.model_dump(),
    )
    session.add(training)
    session.flush()

    apply_ability_delta(
        session,
        ability,
        sentence_assessment_deltas(sentence_feedback.ability_delta),
        TaskType.sentence,
        training.id,
    )

    essay_result = await essay_feedback(
        provider=provider,
        title=ASSESSMENT_ESSAY_TITLE,
        draft=short_writing,
        session=session,
        prompt_version=settings.llm_prompt_version,
        student_id=student.id,
        daily_limit_enabled=settings.llm_daily_limit_enabled,
        daily_limit_per_student_task=settings.llm_daily_limit_per_student_task,
    )
    essay_output = essay_result.output
    essay = Essay(
        student_id=student.id,
        title=ASSESSMENT_ESSAY_TITLE,
        status=ASSESSMENT_ESSAY_STATUS,
    )
    session.add(essay)
    session.flush()

    first_draft = EssayVersion(
        essay_id=essay.id,
        version_label="first_draft",
        content=short_writing,
        ai_feedback=essay_output.model_dump(),
        llm_call_log_id=essay_result.log.id if essay_result.log else None,
    )
    session.add(first_draft)
    session.flush()

    apply_ability_delta(
        session,
        ability,
        draft_ability_deltas(len(essay_output.improvements)),
        TaskType.essay,
        first_draft.id,
    )

    assessment = Assessment(
        student_id=student.id,
        sentence_before=sentence_before,
        sentence_after=sentence_after,
        short_writing=short_writing,
        summary=ASSESSMENT_SUMMARY,
        sentence_training_id=training.id,
        essay_id=essay.id,
    )
    session.add(assessment)
    session.flush()

    settlement = settle_task(
        student,
        TaskType.assessment,
        [],
        {
            "summary": ASSESSMENT_SUMMARY,
            "sentence_training_id": training.id,
            "essay_id": essay.id,
        },
    )
    session.add(student)
    session.add(ability)
    session.add(settlement)

    return EntryAssessmentResult(
        assessment=assessment,
        sentence_training=training,
        essay=essay,
        first_draft=first_draft,
        ability_sketch=to_child_abilities(ability),
        settlement=settlement,
    )
```

- [ ] **Step 3: Rewrite the assessment route**

Replace `apps/api/app/api/routes/assessment.py` with:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps import get_db_session, get_llm_provider
from app.core.config import Settings, get_settings
from app.domain.models import AbilityProfile, StudentProfile
from app.services.assessment import complete_entry_assessment
from app.services.llm_provider import LLMProvider

router = APIRouter(prefix="/api/students", tags=["assessment"])


class AssessmentCreate(BaseModel):
    sentence_before: str = Field(min_length=1, max_length=500)
    sentence_after: str = Field(min_length=1, max_length=500)
    short_writing: str = Field(min_length=20, max_length=500)


@router.post("/{student_id}/assessment", status_code=201)
async def create_assessment(
    student_id: str,
    request: AssessmentCreate,
    session: Session = Depends(get_db_session),
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
):
    student = session.get(StudentProfile, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not student or not ability:
        session.rollback()
        raise HTTPException(status_code=404, detail="student not found")

    try:
        result = await complete_entry_assessment(
            session=session,
            student=student,
            ability=ability,
            provider=provider,
            settings=settings,
            sentence_before=request.sentence_before,
            sentence_after=request.sentence_after,
            short_writing=request.short_writing,
        )
        assessment_payload = {
            "id": result.assessment.id,
            "summary": result.assessment.summary,
            "sentence_training_id": result.assessment.sentence_training_id,
            "essay_id": result.assessment.essay_id,
        }
        settlement_payload = result.settlement.model_dump()
        response_payload = {
            "assessment": assessment_payload,
            "ability_sketch": result.ability_sketch,
            "settlement": settlement_payload,
            "game_event": settlement_payload,
        }
        session.commit()
        return response_payload
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
```

- [ ] **Step 4: Run focused backend tests**

Run:

```bash
cd apps/api
uv run pytest tests/test_assessment_api.py tests/test_auth_assessment_dashboard_api.py::test_assessment_creates_first_ability_sketch_and_dashboard tests/test_essay_workflow_api.py::test_draft_ability_deltas_use_five_unless_exactly_three_improvements -q
```

Expected: PASS.

- [ ] **Step 5: Run route regression tests**

Run:

```bash
cd apps/api
uv run pytest tests/test_sentence_training_api.py tests/test_essay_workflow_api.py tests/test_auth_assessment_dashboard_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/essay_workflow.py apps/api/app/services/assessment.py apps/api/app/api/routes/assessment.py apps/api/app/api/routes/essays.py apps/api/tests/test_essay_workflow_api.py
git commit -m "feat: orchestrate v0.4 entry assessment"
```

---

### Task 5: Backend Verification Sweep

**Files:**
- Modify only files needed to fix focused backend failures from Task 4.

- [ ] **Step 1: Run all backend tests**

Run:

```bash
cd apps/api
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 2: If backend tests fail, fix only the failing contract**

Use the failing assertion to choose the smallest edit. Valid examples:

```python
# If a test still imports draft_ability_deltas from the route:
from app.services.essay_workflow import draft_ability_deltas
```

```python
# If an assessment payload assertion expects only the old game_event key:
assert payload["settlement"]["xp_delta"] == 20
assert payload["game_event"]["xp_delta"] == 20
```

```python
# If an assessment request still allows only 200 writing chars:
short_writing: str = Field(min_length=20, max_length=500)
```

- [ ] **Step 3: Re-run all backend tests**

Run:

```bash
cd apps/api
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 4: Commit backend fixes if any files changed**

```bash
git add apps/api
git commit -m "test: stabilize v0.4 backend assessment coverage"
```

If `git diff -- apps/api` is empty, skip the commit.

---

### Task 6: Update Frontend API Types And Assessment Tests

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/tests/api.test.ts`
- Modify: `apps/web/tests/assessment_sentence_flow.test.tsx`

- [ ] **Step 1: Expand the assessment API response type**

In `apps/web/src/lib/api.ts`, replace `AssessmentResponse` with:

```typescript
export type AbilitySketch = {
  reading_power: number;
  specific_writing_power: number;
  revision_power: number;
};

export type AssessmentResponse = {
  assessment: {
    id: string;
    summary: string;
    sentence_training_id: string;
    essay_id: string;
  };
  ability_sketch: AbilitySketch;
  settlement: Settlement;
  game_event?: Settlement;
};
```

Keep `Settlement` below this block or move `Settlement` above it so TypeScript can resolve the type. If moving it, keep the same `Settlement` fields.

- [ ] **Step 2: Update the API client test response**

In `apps/web/tests/api.test.ts`, replace the mocked response in `createAssessment posts entry trial payload` with:

```typescript
json: async () => ({
  assessment: {
    id: "assessment-1",
    summary: "完成入门小试炼，生成第一张能力草图。",
    sentence_training_id: "sentence-training-1",
    essay_id: "essay-1",
  },
  ability_sketch: {
    reading_power: 40,
    specific_writing_power: 46,
    revision_power: 40,
  },
  settlement: {
    xp_delta: 20,
    level_after: 1,
    badge_code: null,
  },
}),
```

- [ ] **Step 3: Replace the old assessment page test with four-step tests**

In `apps/web/tests/assessment_sentence_flow.test.tsx`, update the default assessment mock in `beforeEach`:

```typescript
apiMocks.createAssessment.mockResolvedValue({
  assessment: {
    id: "assessment-1",
    summary: "完成入门小试炼，生成第一张能力草图。",
    sentence_training_id: "sentence-training-1",
    essay_id: "essay-1",
  },
  ability_sketch: {
    reading_power: 40,
    specific_writing_power: 46,
    revision_power: 40,
  },
  settlement: {
    xp_delta: 20,
    level_after: 1,
    badge_code: null,
  },
});
```

Replace `test("assessment page submits entry trial", ...)` with:

```typescript
test("assessment page renders four steps and submits all fields once", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <AssessmentPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  expect(
    await screen.findByRole("heading", { name: "认识你的写作超能力" }),
  ).toBeInTheDocument();
  expect(screen.getByText("约 3-5 分钟")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "开始小试炼" }));

  expect(screen.getByText("公园很美。")).toBeInTheDocument();
  expect(screen.queryByLabelText("升级前的句子")).not.toBeInTheDocument();
  await userEvent.type(
    screen.getByLabelText("升级后的句子"),
    "公园里的花红红的，风一吹就轻轻摇。",
  );
  await userEvent.click(screen.getByRole("button", { name: "继续写小作文" }));

  expect(screen.getByText("写一写你最近一次开心的经历")).toBeInTheDocument();
  await userEvent.type(
    screen.getByLabelText("小写作"),
    "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
  );
  await userEvent.click(screen.getByRole("button", { name: "生成能力草图" }));

  expect(apiMocks.createAssessment).toHaveBeenCalledTimes(1);
  expect(apiMocks.createAssessment).toHaveBeenCalledWith("s1", {
    sentence_before: "公园很美。",
    sentence_after: "公园里的花红红的，风一吹就轻轻摇。",
    short_writing:
      "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
  });
  expect(
    await screen.findByRole("heading", { name: "第一张能力草图" }),
  ).toBeInTheDocument();
  expect(screen.getByText("写具体力")).toBeInTheDocument();
  expect(screen.getByText("46 / 100")).toBeInTheDocument();
  expect(screen.getByText("等待阅读试炼")).toBeInTheDocument();
  expect(screen.getByText("等待二稿试炼")).toBeInTheDocument();
  expect(screen.getByLabelText("第一张能力草图雷达图")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "回到 Dashboard" })).toHaveAttribute(
    "href",
    "/children/s1",
  );
});
```

Replace `test("assessment page disables submit while pending and reports failures", ...)` with:

```typescript
test("assessment page disables submit while loading and permits retry after failure", async () => {
  let rejectAssessment!: (reason?: unknown) => void;
  apiMocks.createAssessment.mockReturnValueOnce(
    new Promise((_, reject) => {
      rejectAssessment = reject;
    }),
  );

  await act(async () => {
    render(
      <Suspense fallback={null}>
        <AssessmentPage params={Promise.resolve({ studentId: "s1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(await screen.findByRole("button", { name: "开始小试炼" }));
  await userEvent.type(
    screen.getByLabelText("升级后的句子"),
    "公园里的花在风里轻轻摇。",
  );
  await userEvent.click(screen.getByRole("button", { name: "继续写小作文" }));
  await userEvent.type(
    screen.getByLabelText("小写作"),
    "我学会了骑车。刚开始我有点害怕，后来慢慢能骑过小路，我很开心。",
  );
  const submit = screen.getByRole("button", { name: "生成能力草图" });

  await userEvent.click(submit);

  expect(submit).toBeDisabled();
  expect(screen.getByRole("status")).toHaveTextContent(
    "AI 教练正在整理第一张能力草图",
  );

  rejectAssessment(new Error("network"));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "这次小试炼没有提交成功。不是你的问题，检查一下网络后再试一次。",
  );
  await waitFor(() => expect(submit).not.toBeDisabled());
});
```

Append this package guard to the same file:

```typescript
test("assessment sketch uses no charting package", async () => {
  const { readFileSync } = await import("node:fs");
  const packageJson = JSON.parse(
    readFileSync(new URL("../package.json", import.meta.url), "utf8"),
  );

  expect(packageJson.dependencies).not.toHaveProperty("recharts");
  expect(packageJson.dependencies).not.toHaveProperty("chart.js");
  expect(packageJson.dependencies).not.toHaveProperty("@nivo/radar");
});
```

- [ ] **Step 4: Run focused frontend tests and confirm failures**

Run:

```bash
cd apps/web
corepack pnpm exec vitest run tests/api.test.ts tests/assessment_sentence_flow.test.tsx --environment jsdom
```

Expected: FAIL because the page still renders the old bare form and the response type may not match yet.

- [ ] **Step 5: Commit the failing frontend tests and type contract**

```bash
git add apps/web/src/lib/api.ts apps/web/tests/api.test.ts apps/web/tests/assessment_sentence_flow.test.tsx
git commit -m "test: define v0.4 assessment frontend flow"
```

---

### Task 7: Implement Four-Step Assessment UI

**Files:**
- Modify: `apps/web/src/app/children/[studentId]/assessment/page.tsx`

- [ ] **Step 1: Replace the assessment page**

Replace `apps/web/src/app/children/[studentId]/assessment/page.tsx` with:

```typescript
"use client";

import Link from "next/link";
import { ArrowRight, RotateCcw, Sparkles } from "lucide-react";
import { use, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { createAssessment } from "../../../../lib/api";
import type { AbilitySketch, AssessmentResponse } from "../../../../lib/api";

const FIXED_SOURCE_SENTENCE = "公园很美。";
const WRITING_PROMPT = "写一写你最近一次开心的经历";

type Step = "intro" | "sentence" | "writing" | "sketch";

const abilityLabels = {
  reading_power: "读懂力",
  specific_writing_power: "写具体力",
  revision_power: "会修改力",
} as const;

type AbilityKey = keyof typeof abilityLabels;

function radarPoint(index: number, value: number) {
  const angle = -Math.PI / 2 + index * ((Math.PI * 2) / 3);
  const radius = (Math.max(0, Math.min(100, value)) / 100) * 58;
  const center = 80;
  return {
    x: center + Math.cos(angle) * radius,
    y: center + Math.sin(angle) * radius,
  };
}

function polygonPoints(sketch: AbilitySketch) {
  return (Object.keys(abilityLabels) as AbilityKey[])
    .map((key, index) => {
      const point = radarPoint(index, sketch[key]);
      return `${point.x},${point.y}`;
    })
    .join(" ");
}

function strongestSignal(sketch: AbilitySketch) {
  const entries = (Object.keys(abilityLabels) as AbilityKey[]).map((key) => ({
    key,
    value: sketch[key],
  }));
  const strongest = entries.reduce((best, item) =>
    item.value > best.value ? item : best,
  );

  if (strongest.key === "specific_writing_power") {
    return "写具体力已经露出第一个亮点。";
  }
  if (strongest.key === "reading_power") {
    return "读懂力保持稳定，后面可以用阅读试炼点亮更多证据。";
  }
  return "会修改力保持稳定，二稿任务会继续点亮它。";
}

function AbilityRadar({ sketch }: { sketch: AbilitySketch }) {
  const keys = Object.keys(abilityLabels) as AbilityKey[];
  const guide = "80,22 130.229,109 29.771,109";

  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr] lg:items-center">
      <svg
        viewBox="0 0 160 150"
        role="img"
        aria-label="第一张能力草图雷达图"
        className="h-56 w-full max-w-64 justify-self-center"
      >
        <polygon
          points={guide}
          fill="none"
          stroke="var(--wen-border)"
          strokeWidth="2"
        />
        <polygon
          points="80,41.333 113.486,99 46.514,99"
          fill="none"
          stroke="var(--wen-border)"
          strokeWidth="1"
        />
        <polygon
          points={polygonPoints(sketch)}
          fill="rgba(74, 168, 255, 0.24)"
          stroke="var(--wen-sky)"
          strokeWidth="3"
          strokeLinejoin="round"
        />
        {keys.map((key, index) => {
          const point = radarPoint(index, sketch[key]);
          return (
            <circle
              key={key}
              cx={point.x}
              cy={point.y}
              r="4"
              fill="var(--wen-orange)"
            />
          );
        })}
        <text x="80" y="14" textAnchor="middle" className="fill-[var(--wen-ink)] text-[9px]">
          读懂力
        </text>
        <text x="145" y="124" textAnchor="middle" className="fill-[var(--wen-ink)] text-[9px]">
          写具体力
        </text>
        <text x="15" y="124" textAnchor="middle" className="fill-[var(--wen-ink)] text-[9px]">
          会修改力
        </text>
      </svg>
      <div className="space-y-3">
        <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
          {strongestSignal(sketch)}
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          {keys.map((key) => {
            const waiting =
              key === "reading_power" && sketch[key] === 40
                ? "等待阅读试炼"
                : key === "revision_power" && sketch[key] === 40
                  ? "等待二稿试炼"
                  : `${sketch[key]} / 100`;

            return (
              <div
                key={key}
                className="rounded-lg border border-[var(--wen-border)] bg-white p-3"
              >
                <p className="font-semibold">{abilityLabels[key]}</p>
                <p className="mt-1 text-sm text-[var(--wen-muted)]">{waiting}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function AssessmentPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);
  const [step, setStep] = useState<Step>("intro");
  const [sentenceAfter, setSentenceAfter] = useState("");
  const [shortWriting, setShortWriting] = useState("");
  const [result, setResult] = useState<AssessmentResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const canContinueSentence = sentenceAfter.trim().length > 0;
  const canSubmitWriting = shortWriting.trim().length >= 20;
  const progress = useMemo(
    () =>
      [
        { key: "intro", label: "开始" },
        { key: "sentence", label: "句子魔法" },
        { key: "writing", label: "小写作" },
        { key: "sketch", label: "能力草图" },
      ] as const,
    [],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmitWriting || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError("");

    try {
      const response = await createAssessment(studentId, {
        sentence_before: FIXED_SOURCE_SENTENCE,
        sentence_after: sentenceAfter,
        short_writing: shortWriting,
      });

      setResult(response);
      setStep("sketch");
    } catch {
      setError("这次小试炼没有提交成功。不是你的问题，检查一下网络后再试一次。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <nav aria-label="小试炼进度" className="flex flex-wrap gap-2 text-sm font-semibold">
          {progress.map((item) => (
            <span
              key={item.key}
              className={`rounded-lg px-3 py-2 ${
                step === item.key
                  ? "bg-[var(--wen-orange)] text-white"
                  : "bg-white text-[var(--wen-muted)]"
              }`}
            >
              {item.label}
            </span>
          ))}
        </nav>

        {step === "intro" ? (
          <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
            <p className="text-sm font-semibold text-[var(--wen-muted)]">约 3-5 分钟</p>
            <h1 className="mt-3 text-3xl font-bold">认识你的写作超能力</h1>
            <p className="mt-4 text-[var(--wen-muted)]">
              先完成一句话升级，再写一小段开心经历。
            </p>
            <button
              type="button"
              onClick={() => setStep("sentence")}
              className="mt-6 inline-flex items-center gap-2 rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white shadow-sm"
            >
              <Sparkles size={18} aria-hidden="true" />
              开始小试炼
            </button>
          </section>
        ) : null}

        {step === "sentence" ? (
          <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
            <h1 className="text-2xl font-bold">句子魔法</h1>
            <div className="mt-5 rounded-lg bg-[var(--wen-bg)] p-4">
              <p className="text-sm font-semibold text-[var(--wen-muted)]">原句</p>
              <p className="mt-2 text-xl font-bold">{FIXED_SOURCE_SENTENCE}</p>
            </div>
            <label className="mt-5 block font-semibold">
              升级后的句子
              <textarea
                value={sentenceAfter}
                onChange={(event) => setSentenceAfter(event.target.value)}
                maxLength={500}
                className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
              />
            </label>
            <button
              type="button"
              onClick={() => setStep("writing")}
              disabled={!canContinueSentence}
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              继续写小作文
              <ArrowRight size={18} aria-hidden="true" />
            </button>
          </section>
        ) : null}

        {step === "writing" ? (
          <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
            <h1 className="text-2xl font-bold">小写作</h1>
            <p className="mt-3 rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
              {WRITING_PROMPT}
            </p>
            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
              <label className="block font-semibold">
                小写作
                <textarea
                  value={shortWriting}
                  onChange={(event) => setShortWriting(event.target.value)}
                  minLength={20}
                  maxLength={500}
                  className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
                />
              </label>
              <button
                type="submit"
                disabled={!canSubmitWriting || isSubmitting}
                className="inline-flex items-center gap-2 rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Sparkles size={18} aria-hidden="true" />
                生成能力草图
              </button>
            </form>
            {isSubmitting ? (
              <p role="status" className="mt-4 text-sm font-semibold text-[var(--wen-muted)]">
                AI 教练正在整理第一张能力草图
              </p>
            ) : null}
            {error ? (
              <div role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">
                <p>{error}</p>
                <button
                  type="button"
                  onClick={() => setError("")}
                  className="mt-3 inline-flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-[var(--wen-ink)]"
                >
                  <RotateCcw size={16} aria-hidden="true" />
                  再试一次
                </button>
              </div>
            ) : null}
          </section>
        ) : null}

        {step === "sketch" && result ? (
          <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
            <p className="text-sm font-semibold text-[var(--wen-muted)]">
              {result.assessment.summary}
            </p>
            <h1 className="mt-3 text-2xl font-bold">第一张能力草图</h1>
            <div className="mt-6">
              <AbilityRadar sketch={result.ability_sketch} />
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <span className="rounded-lg bg-[var(--wen-bg)] px-3 py-2 text-sm font-semibold">
                +{result.settlement.xp_delta} XP
              </span>
              <Link
                href={`/children/${studentId}`}
                className="inline-flex items-center gap-2 rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white"
              >
                回到 Dashboard
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Run focused frontend tests**

Run:

```bash
cd apps/web
corepack pnpm exec vitest run tests/api.test.ts tests/assessment_sentence_flow.test.tsx --environment jsdom
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/children/[studentId]/assessment/page.tsx
git commit -m "feat: add v0.4 assessment entry flow"
```

---

### Task 8: Add E2E Assessment Flow And Manual QA Notes

**Files:**
- Modify: `apps/web/e2e/mvp.spec.ts`
- Create: `qa/2026-05-21-v0.4-minimal-assessment-manual-qa.md`

- [ ] **Step 1: Add a Playwright default-child seed helper**

In `apps/web/e2e/mvp.spec.ts`, add this import at the top:

```typescript
import { execFileSync } from "node:child_process";
```

Below `test.use(...)`, add:

```typescript
function seedDefaultAssessmentChild() {
  execFileSync(
    "uv",
    [
      "run",
      "python",
      "-c",
      [
        "from sqlmodel import Session, create_engine",
        "from app.domain.models import AbilityProfile, ParentUser, StudentProfile",
        "engine = create_engine('sqlite:///./playwright-e2e.db')",
        "with Session(engine) as session:",
        "    if session.get(StudentProfile, 'e2e-assessment-child') is None:",
        "        parent = ParentUser(id='e2e-assessment-parent', email='e2e-assessment@example.com', display_name='E2E Parent')",
        "        student = StudentProfile(id='e2e-assessment-child', parent_id=parent.id, name='小测', persona='real_child', is_real_child=True)",
        "        ability = AbilityProfile(student_id=student.id)",
        "        session.add(parent)",
        "        session.add(student)",
        "        session.add(ability)",
        "        session.commit()",
      ].join("; "),
    ],
    {
      cwd: "../api",
      env: {
        ...process.env,
        DATABASE_URL: process.env.PLAYWRIGHT_DATABASE_URL ?? "sqlite:///./playwright-e2e.db",
      },
    },
  );
}
```

- [ ] **Step 2: Add the assessment E2E test**

Append this test above the existing MVP demo flow test:

```typescript
test("default child completes assessment and returns to non-assessment dashboard recommendation", async ({
  page,
}) => {
  seedDefaultAssessmentChild();

  await page.goto("/children/e2e-assessment-child");

  await expect(page.getByRole("heading", { name: "小测的小文星球" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "入门小试炼" })).toBeVisible();
  await page
    .getByRole("article")
    .filter({ hasText: "入门小试炼" })
    .getByRole("link", { name: "开始任务" })
    .click();

  await expect(
    page.getByRole("heading", { name: "认识你的写作超能力" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "开始小试炼" }).click();
  await expect(page.getByText("公园很美。")).toBeVisible();
  await page
    .getByLabel("升级后的句子")
    .fill("公园里的花红红的，风一吹就轻轻摇。");
  await page.getByRole("button", { name: "继续写小作文" }).click();
  await page
    .getByLabel("小写作")
    .fill("我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。");
  await page.getByRole("button", { name: "生成能力草图" }).click();

  await expect(page.getByRole("heading", { name: "第一张能力草图" })).toBeVisible();
  await expect(page.getByText("写具体力")).toBeVisible();
  await expect(page.getByText("等待阅读试炼")).toBeVisible();
  await expect(page.getByText("等待二稿试炼")).toBeVisible();

  await page.getByRole("link", { name: "回到 Dashboard" }).click();
  await expect(page.getByText("第一张能力草图")).toBeVisible();
  await expect(page.getByRole("heading", { name: "作文城堡" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "入门小试炼" })).toHaveCount(0);
});
```

- [ ] **Step 3: Create manual QA notes**

Create `qa/2026-05-21-v0.4-minimal-assessment-manual-qa.md`:

```markdown
# WenLingo V0.4 Minimal Assessment Manual QA

Date: 2026-05-21
Status: Ready for execution after implementation

## Preflight

- Remove stale SQLite files using `qa/2026-05-21-stale-sqlite-cleanup.md`.
- Start API and web with mock LLM unless a real-LLM spot check is being recorded.

## Stopwatch Timing

- Start timing when the child clicks `开始小试炼`.
- Stop timing when `第一张能力草图` appears.
- Pass condition: a normal child-friendly manual run completes within 3-5 minutes.

## Checks

- Intro shows `认识你的写作超能力` and `约 3-5 分钟`.
- Sentence step displays fixed source sentence `公园很美。` and does not allow editing that source.
- Short-writing step uses prompt `写一写你最近一次开心的经历`.
- Submit loading copy says `AI 教练正在整理第一张能力草图`.
- Error copy invites retry and does not blame the child.
- Ability sketch shows an inline triangular radar chart plus all three labels.
- `读懂力` at 40 displays `等待阅读试炼`.
- `会修改力` at 40 displays `等待二稿试炼`.
- Returning to Dashboard shows `第一张能力草图`.
- New/default child no longer receives `入门小试炼` as the main recommendation after completion.
- Existing demo family dashboard and report flow still pass.

## Real LLM Spot Check

If using a real provider, record provider, model, prompt version, whether fallback triggered, and whether the feedback stayed coaching-only without ghostwriting.
```

- [ ] **Step 4: Run E2E**

Remove stale Playwright SQLite first:

```powershell
if (Test-Path -LiteralPath "apps/api/playwright-e2e.db") {
  Remove-Item -LiteralPath "apps/api/playwright-e2e.db"
}
```

Run:

```bash
cd apps/web
corepack pnpm e2e -- mvp.spec.ts
```

Expected: PASS for both the new assessment E2E and the existing MVP demo flow.

- [ ] **Step 5: Commit**

```bash
git add apps/web/e2e/mvp.spec.ts qa/2026-05-21-v0.4-minimal-assessment-manual-qa.md
git commit -m "test: cover v0.4 assessment e2e flow"
```

---

### Task 9: Final Verification

**Files:**
- Modify only files needed to fix verification failures.

- [ ] **Step 1: Run backend suite**

Run:

```bash
cd apps/api
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend unit suite**

Run:

```bash
cd apps/web
corepack pnpm test
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd apps/web
corepack pnpm build
```

Expected: PASS.

- [ ] **Step 4: Run E2E**

Remove stale Playwright SQLite first:

```powershell
if (Test-Path -LiteralPath "apps/api/playwright-e2e.db") {
  Remove-Item -LiteralPath "apps/api/playwright-e2e.db"
}
```

Run:

```bash
cd apps/web
corepack pnpm e2e -- mvp.spec.ts
```

Expected: PASS.

- [ ] **Step 5: Inspect dependency changes**

Run:

```bash
git diff -- apps/web/package.json apps/web/pnpm-lock.yaml
```

Expected: no charting dependency such as `recharts`, `chart.js`, or `@nivo/radar`.

- [ ] **Step 6: Commit final verification fixes if any files changed**

```bash
git add apps/api apps/web README.md qa
git commit -m "chore: finalize v0.4 assessment verification"
```

If there are no changes after verification, skip the commit.

---

## Self-Review

### Spec Coverage

- V0.3 release note: Task 1 creates `qa/2026-05-21-v0.3-release-note.md`.
- Stale SQLite cleanup docs: Task 1 creates `qa/2026-05-21-stale-sqlite-cleanup.md` and links it from `README.md`.
- Assessment artifact references: Task 2 updates `Assessment` and migration.
- Backend service orchestrator: Task 4 creates `app.services.assessment.complete_entry_assessment`.
- Thin route with rollback and single commit: Task 4 rewrites `routes/assessment.py`.
- Existing LLM wrappers: Task 4 calls `sentence_upgrade_feedback` and `essay_feedback` directly.
- `SentenceFocus.detail.value`: Task 4 uses the verified enum member.
- Sentence training artifact: Tasks 3 and 4 create and test `SentenceTraining`.
- Essay and first `EssayVersion` artifact: Tasks 3 and 4 create and test assessment-only essay artifacts.
- Assessment-only essay status: Tasks 3 and 4 use and test `ASSESSMENT_ESSAY_STATUS`.
- Ability history source types: Task 3 asserts sentence and essay source links only.
- Ability profile changes from default: Task 3 asserts expression, observation, and structure changes.
- Response includes `ability_sketch` and `settlement`: Tasks 3, 4, and 6 cover response shape.
- Dashboard no longer recommends assessment after completion: Tasks 3 and 8 cover backend and E2E transition.
- Schema-valid fallback completes: Task 3 covers invalid provider fallback.
- Ghostwriting and unhandled errors roll back: Task 3 covers both rollback cases.
- Overlong inputs return 422: Task 3 covers sentence and writing max lengths.
- Demo family stable: Task 3 updates only the assessment test; Task 5 runs dashboard/auth regressions; Task 8 keeps the MVP E2E.
- Four-step frontend flow: Tasks 6 and 7 cover intro, sentence, writing, sketch.
- Fixed source sentence: Tasks 6 and 7 cover display-only `公园很美。`.
- Loading and retry states: Tasks 6 and 7 cover loading copy and retry after failure.
- Inline SVG radar and no chart dependency: Tasks 6, 7, and 9 cover implementation and dependency guard.
- Manual QA timing and copy checks: Task 8 creates the manual QA note.

### Placeholder Scan

The plan contains no unresolved placeholder markers, no empty future work markers, no unresolved type names, and no steps that ask the implementer to invent behavior without concrete file paths, commands, or code snippets.

### Type Consistency

- Backend response uses `ability_sketch` and `settlement`; `game_event` remains an optional compatibility alias.
- Artifact IDs are named `sentence_training_id` and `essay_id` in model, migration, route, API type, tests, and E2E expectations.
- Shared essay status is consistently `ASSESSMENT_ESSAY_STATUS = "assessment_completed"`.
- Frontend ability keys match `to_child_abilities`: `reading_power`, `specific_writing_power`, and `revision_power`.
