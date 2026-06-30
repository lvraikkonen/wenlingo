from datetime import timedelta

import pytest
from sqlalchemy import desc
from sqlmodel import select

from app.domain.models import Essay, EssayRevisionAttempt, EssayVersion, utcnow
from app.services import essay_archive


def test_version_label_for_round_is_stable_and_legacy_compatible():
    assert essay_archive.get_version_label_for_round(1) == "first_draft"
    assert essay_archive.get_version_label_for_round(2) == "revision"
    assert essay_archive.get_version_label_for_round(3) == "revision_round_3"
    assert essay_archive.get_version_label_for_round(4) == "revision_round_4"


def test_get_round_index_reads_new_field_and_legacy_labels():
    assert (
        essay_archive.get_round_index(
            EssayVersion(
                essay_id="e",
                version_label="first_draft",
                content="x",
                round_index=1,
            )
        )
        == 1
    )
    assert (
        essay_archive.get_round_index(
            EssayVersion(
                essay_id="e",
                version_label="revision",
                content="x",
                round_index=2,
            )
        )
        == 2
    )
    assert (
        essay_archive.get_round_index(
            EssayVersion(essay_id="e", version_label="revision", content="x")
        )
        == 2
    )


@pytest.mark.parametrize("round_index", [0, -1])
def test_version_label_for_round_rejects_non_positive_rounds(round_index):
    with pytest.raises(ValueError, match="round_index must be positive"):
        essay_archive.get_version_label_for_round(round_index)


@pytest.mark.parametrize(
    "version",
    [
        EssayVersion(essay_id="e", version_label="first_draft", content="x", round_index=0),
        EssayVersion(essay_id="e", version_label="revision", content="x", round_index=-1),
        EssayVersion(essay_id="e", version_label="unknown", content="x"),
        EssayVersion(essay_id="e", version_label="revision_round_", content="x"),
        EssayVersion(essay_id="e", version_label="revision_round_0", content="x"),
        EssayVersion(essay_id="e", version_label="revision_round_abc", content="x"),
    ],
)
def test_get_round_index_rejects_invalid_rounds_and_labels(version):
    with pytest.raises(ValueError):
        essay_archive.get_round_index(version)


def _add_essay_with_versions(
    session,
    *,
    essay_id: str,
    title: str,
    rounds: int,
    status: str = "settled",
    hidden_by: str = "",
    submitted_at=None,
    outline: dict | None = None,
    material_card: dict | None = None,
) -> Essay:
    now = submitted_at or utcnow()
    essay = Essay(
        id=essay_id,
        student_id="student-1",
        title=title,
        status=status,
        hidden_by=hidden_by,
        hidden_at=now if hidden_by else None,
        visibility_changed_at=now if hidden_by else None,
        last_version_submitted_at=now,
        outline=outline or {},
        material_card=material_card or {},
    )
    session.add(essay)
    session.flush()

    for round_index in range(1, rounds + 1):
        ai_feedback = {}
        if round_index == 1:
            ai_feedback = {
                "revision_tasks": [
                    {"instruction": "先补一个清楚的开头。"},
                    {"text": "再写一个具体细节。"},
                ]
            }
        elif round_index >= 2:
            ai_feedback = {"next_step": f"第 {round_index} 稿下一步建议"}
        session.add(
            EssayVersion(
                id=f"{essay_id}-v{round_index}",
                essay_id=essay.id,
                version_label=essay_archive.get_version_label_for_round(round_index),
                round_index=round_index,
                content=f"{title} 第 {round_index} 稿",
                ai_feedback=ai_feedback,
                created_at=now + timedelta(minutes=round_index),
            )
        )

    session.commit()
    session.refresh(essay)
    return essay


def test_archive_status_distinguishes_revision_states(session):
    round_one = _add_essay_with_versions(
        session,
        essay_id="round-one",
        title="只写了一稿",
        rounds=1,
    )
    item = essay_archive.build_archive_item(
        session,
        round_one,
        parent_visible=False,
        child_surface=True,
    )
    assert item["status"] == "needs_revision"
    assert item["needs_revision"] is True
    assert item["can_continue_revision"] is True
    assert item["can_retry_revision_attempt"] is False
    assert item["summary_label"]

    round_two = _add_essay_with_versions(
        session,
        essay_id="round-two",
        title="修改了一次",
        rounds=2,
    )
    item = essay_archive.build_archive_item(
        session,
        round_two,
        parent_visible=False,
        child_surface=True,
    )
    assert item["status"] == "revised_once"
    assert item["needs_revision"] is False
    assert item["can_continue_revision"] is True
    assert item["can_retry_revision_attempt"] is False
    assert item["summary_label"]

    round_three = _add_essay_with_versions(
        session,
        essay_id="round-three",
        title="多轮修改",
        rounds=3,
    )
    item = essay_archive.build_archive_item(
        session,
        round_three,
        parent_visible=False,
        child_surface=True,
    )
    assert item["status"] == "multi_round_revision"
    assert item["latest_round_index"] == 3
    assert item["revision_round_count"] == 2
    assert item["needs_revision"] is False
    assert item["can_continue_revision"] is True
    assert item["can_retry_revision_attempt"] is False
    assert item["summary_label"]

    hidden = _add_essay_with_versions(
        session,
        essay_id="hidden-by-child",
        title="孩子隐藏",
        rounds=3,
        hidden_by="child",
    )
    item = essay_archive.build_archive_item(
        session,
        hidden,
        parent_visible=True,
        child_surface=False,
    )
    assert item["status"] == "hidden_by_child"
    assert item["hidden"] is True
    assert item["hidden_by"] == "child"
    assert item["needs_revision"] is False
    assert item["can_continue_revision"] is False
    assert item["can_retry_revision_attempt"] is False
    assert item["summary_label"]

    failed = _add_essay_with_versions(
        session,
        essay_id="failed-latest",
        title="比较失败",
        rounds=2,
    )
    session.add(
        EssayRevisionAttempt(
            essay_id=failed.id,
            base_version_id="failed-latest-v2",
            target_round_index=3,
            submitted_content="第三稿内容",
            submitted_content_hash="hash-failed",
            idempotency_key="idem-failed",
            status="comparison_failed",
            error_code="llm_timeout",
        )
    )
    session.commit()
    item = essay_archive.build_archive_item(
        session,
        failed,
        parent_visible=False,
        child_surface=True,
    )
    assert item["status"] == "needs_retry"
    assert item["needs_revision"] is True
    assert item["can_continue_revision"] is True
    assert item["can_retry_revision_attempt"] is True
    assert item["summary_label"]


def test_archive_status_requires_first_draft_round(session):
    essay = Essay(
        id="missing-first-draft",
        student_id="student-1",
        title="缺少初稿",
        status="settled",
        last_version_submitted_at=utcnow(),
    )
    session.add(essay)
    session.flush()
    session.add(
        EssayVersion(
            id="missing-first-draft-v2",
            essay_id=essay.id,
            version_label="revision",
            round_index=2,
            content="只有第二稿",
        )
    )
    session.commit()

    item = essay_archive.build_archive_item(
        session,
        essay,
        parent_visible=False,
        child_surface=True,
    )

    assert item["status"] == "not_archived"
    assert item["latest_round_index"] == 2
    assert item["needs_revision"] is False
    assert item["can_continue_revision"] is False


def test_child_archive_recency_uses_submission_time_and_preserves_topic_metadata(session):
    now = utcnow()
    older = _add_essay_with_versions(
        session,
        essay_id="older-restored",
        title="旧作文",
        rounds=2,
        submitted_at=now - timedelta(days=3),
        outline={"topic_origin": "teacher_provided"},
    )
    _add_essay_with_versions(
        session,
        essay_id="newer-submission",
        title="AI 灵感作文",
        rounds=1,
        submitted_at=now - timedelta(hours=1),
        outline={
            "topic_origin": "ai_topic_idea",
            "selected_topic_idea": {
                "idea_id": "idea-1",
                "title": "雨天里的发现",
            },
            "scaffold": {
                "topic_type": "personal_narrative",
                "topic_variant": "rainy_day",
                "scaffold_template_version": "v0.6c",
            },
        },
    )
    hidden = _add_essay_with_versions(
        session,
        essay_id="hidden-child",
        title="隐藏作文",
        rounds=1,
        hidden_by="child",
        submitted_at=now,
    )
    session.add(hidden)
    session.commit()

    def child_items():
        essays = session.exec(
            select(Essay)
            .where(Essay.student_id == "student-1", Essay.hidden_by == "")
            .order_by(desc(Essay.last_version_submitted_at))
        ).all()
        return [
            essay_archive.build_archive_item(
                session,
                essay,
                parent_visible=False,
                child_surface=True,
            )
            for essay in essays
        ]

    child_archive_items = child_items()
    assert [item["essay_id"] for item in child_archive_items] == [
        "newer-submission",
        "older-restored",
    ]
    assert child_archive_items[0]["topic_origin"] == "ai_topic_idea"
    assert child_archive_items[0]["topic_type"] == "personal_narrative"
    assert child_archive_items[0]["topic_variant"] == "rainy_day"
    assert child_archive_items[0]["scaffold_template_version"] == "v0.6c"
    assert child_archive_items[0]["generated_topic_metadata"]["idea_id"] == "idea-1"

    older.visibility_changed_at = now + timedelta(days=1)
    session.add(older)
    session.commit()

    child_archive_items = child_items()
    assert [item["essay_id"] for item in child_archive_items] == [
        "newer-submission",
        "older-restored",
    ]


def test_archive_detail_includes_timeline_continue_guidance_retry_and_parent_summary(session):
    essay = _add_essay_with_versions(
        session,
        essay_id="detail-essay",
        title="详情作文",
        rounds=2,
    )
    session.add(
        EssayRevisionAttempt(
            essay_id=essay.id,
            base_version_id="detail-essay-v2",
            target_round_index=3,
            submitted_content="第三稿内容",
            submitted_content_hash="hash-detail",
            idempotency_key="idem-detail",
            status="comparison_failed",
            error_code="llm_timeout",
        )
    )
    session.commit()

    detail = essay_archive.build_archive_detail(
        session,
        essay,
        parent_visible=False,
        child_surface=True,
    )

    assert detail["essay_id"] == "detail-essay"
    assert detail["status"] == "needs_retry"
    assert [version["round_index"] for version in detail["versions"]] == [1, 2]
    assert detail["continue_revision"] == {
        "latest_version_id": "detail-essay-v2",
        "latest_content": "详情作文 第 2 稿",
        "previous_ai_guidance": "上次 AI 对比没有完成（llm_timeout）。请重新提交这一稿，我们会继续帮你比较修改。",
        "next_round_index": 3,
    }
    assert detail["revision_attempt"]["can_retry"] is True
    assert detail["revision_attempt"]["error_code"] == "llm_timeout"
    assert detail["parent_summary"]["latest_round_index"] == 2
    assert detail["parent_summary"]["summary_label"]
