from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import update
from sqlmodel import Session, select

from app.domain.models import Essay, WritingTopicIdeaBatch, utcnow
from app.services.llm_contracts import WritingTopicIdeasResult
from app.services.writing_topic_ideas import (
    AI_TOPIC_ORIGIN,
    create_idea_batch,
    create_or_return_ai_topic_essay,
    select_idea_from_batch,
)
from tests.conftest import create_authenticated_family


def _ideas() -> WritingTopicIdeasResult:
    return WritingTopicIdeasResult(
        ideas=[
            {
                "id": "idea-1",
                "title": "足球训练里的小挑战",
                "topic_type": "generic_narrative",
                "topic_variant": "default",
                "why_it_fits_child_interest": "喜欢足球，可以从一次训练开始想。",
                "practice_focus": "把顺序和关键动作说清楚",
                "child_safe_prompt": "你想写哪一次足球训练？先选一个真实画面。",
            },
            {
                "id": "idea-2",
                "title": "我推荐的小公园",
                "topic_type": "place_scenery",
                "topic_variant": "place_recommendation",
                "why_it_fits_child_interest": "可以写自己熟悉又喜欢的地方。",
                "practice_focus": "练习有顺序地介绍景物",
                "child_safe_prompt": "你会推荐公园里的哪一处？先写你看到的细节。",
            },
            {
                "id": "idea-3",
                "title": "给朋友的一封信",
                "topic_type": "practical_writing",
                "topic_variant": "letter",
                "why_it_fits_child_interest": "可以从真实想说的话开始。",
                "practice_focus": "练习把事情和心情说清楚",
                "child_safe_prompt": "你最想告诉朋友哪件事？先写一句真心话。",
            },
        ]
    )


def test_create_idea_batch_persists_provenance(session):
    family = create_authenticated_family(session)
    student = family["student"]

    batch = create_idea_batch(
        session,
        student=student,
        ideas=_ideas(),
        interest_text=" 足球 ",
    )
    session.commit()

    saved = session.get(WritingTopicIdeaBatch, batch.id)
    assert saved is not None
    assert saved.student_id == student.id
    assert saved.grade_label == "四年级"
    assert saved.interest_input_present is True
    assert [idea["id"] for idea in saved.ideas] == ["idea-1", "idea-2", "idea-3"]
    assert saved.expires_at > saved.created_at
    assert saved.consumed_at is None
    assert saved.selected_idea_id == ""
    assert saved.created_essay_id is None


def test_select_idea_from_batch_does_not_require_session(session):
    family = create_authenticated_family(session)
    batch = create_idea_batch(
        session,
        student=family["student"],
        ideas=_ideas(),
        interest_text="足球",
    )

    selected = select_idea_from_batch(batch=batch, selected_idea_id="idea-1")

    assert selected["id"] == "idea-1"


def test_create_or_return_ai_topic_essay_is_idempotent_for_same_selection(session):
    family = create_authenticated_family(session)
    student = family["student"]
    batch = create_idea_batch(
        session,
        student=student,
        ideas=_ideas(),
        interest_text="足球",
    )
    session.commit()

    essay, selected, created = create_or_return_ai_topic_essay(
        session,
        student=student,
        batch=batch,
        selected_idea_id="idea-1",
    )
    session.commit()

    assert created is True
    assert selected["id"] == "idea-1"
    assert essay.title == "足球训练里的小挑战"
    assert essay.status == "prewriting_started"
    assert essay.outline["topic_origin"] == AI_TOPIC_ORIGIN
    assert essay.outline["selected_topic_idea"]["id"] == "idea-1"
    assert essay.outline["topic_requirement"] == {
        "topic_text": "足球训练里的小挑战",
        "child_safe_prompt": "你想写哪一次足球训练？先选一个真实画面。",
        "source": AI_TOPIC_ORIGIN,
    }
    assert essay.outline["scaffold"]["selection_source"] == "ai_suggested"
    assert essay.material_card["scaffold_ref"]["topic_type"] == "generic_narrative"

    session.refresh(batch)
    assert batch.consumed_at is not None
    assert batch.selected_idea_id == "idea-1"
    assert batch.created_essay_id == essay.id

    returned, returned_selected, returned_created = create_or_return_ai_topic_essay(
        session,
        student=student,
        batch=batch,
        selected_idea_id="idea-1",
    )

    assert returned.id == essay.id
    assert returned_selected["id"] == "idea-1"
    assert returned_created is False
    assert len(session.exec(select(Essay)).all()) == 1


def test_create_or_return_ai_topic_essay_rejects_forged_idea_id_without_creating_essay(session):
    family = create_authenticated_family(session)
    student = family["student"]
    batch = create_idea_batch(
        session,
        student=student,
        ideas=_ideas(),
        interest_text="足球",
    )
    session.commit()

    with pytest.raises(HTTPException) as exc_info:
        create_or_return_ai_topic_essay(
            session,
            student=student,
            batch=batch,
            selected_idea_id="forged-idea",
        )

    assert exc_info.value.status_code == 400
    assert len(session.exec(select(Essay)).all()) == 0


def test_create_or_return_ai_topic_essay_rejects_expired_batch(session):
    family = create_authenticated_family(session)
    student = family["student"]
    batch = create_idea_batch(
        session,
        student=student,
        ideas=_ideas(),
        interest_text="足球",
    )
    batch.expires_at = utcnow() - timedelta(minutes=1)
    session.add(batch)
    session.commit()

    with pytest.raises(HTTPException) as exc_info:
        create_or_return_ai_topic_essay(
            session,
            student=student,
            batch=batch,
            selected_idea_id="idea-1",
        )

    assert exc_info.value.status_code == 410
    assert len(session.exec(select(Essay)).all()) == 0


def test_create_or_return_ai_topic_essay_rejects_consumed_batch_with_different_selection(session):
    family = create_authenticated_family(session)
    student = family["student"]
    batch = create_idea_batch(
        session,
        student=student,
        ideas=_ideas(),
        interest_text="足球",
    )
    essay, _selected, created = create_or_return_ai_topic_essay(
        session,
        student=student,
        batch=batch,
        selected_idea_id="idea-1",
    )
    session.commit()

    assert created is True

    with pytest.raises(HTTPException) as exc_info:
        create_or_return_ai_topic_essay(
            session,
            student=student,
            batch=batch,
            selected_idea_id="idea-2",
        )

    assert exc_info.value.status_code == 409
    assert [saved.id for saved in session.exec(select(Essay)).all()] == [essay.id]


def test_create_or_return_ai_topic_essay_returns_existing_essay_after_stale_race(session):
    family = create_authenticated_family(session)
    student = family["student"]
    batch = create_idea_batch(
        session,
        student=student,
        ideas=_ideas(),
        interest_text="足球",
    )
    session.commit()
    session.refresh(batch)

    with Session(session.get_bind()) as racing_session:
        essay = Essay(
            student_id=student.id,
            title="足球训练里的小挑战",
            status="prewriting_started",
            material_card={},
            outline={},
        )
        racing_session.add(essay)
        racing_session.flush()
        racing_session.exec(
            update(WritingTopicIdeaBatch)
            .where(WritingTopicIdeaBatch.id == batch.id)
            .values(
                consumed_at=utcnow(),
                selected_idea_id="idea-1",
                created_essay_id=essay.id,
            )
        )
        racing_session.commit()
        essay_id = essay.id

    returned, selected, created = create_or_return_ai_topic_essay(
        session,
        student=student,
        batch=batch,
        selected_idea_id="idea-1",
    )

    assert returned.id == essay_id
    assert selected["id"] == "idea-1"
    assert created is False
    assert len(session.exec(select(Essay)).all()) == 1
