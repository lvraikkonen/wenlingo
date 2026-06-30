from datetime import timedelta
from datetime import timezone

from sqlalchemy.dialects import postgresql
from sqlmodel import select

from app.domain.enums import TaskType
from app.domain.models import (
    AbilityHistory,
    Essay,
    EssayVersion,
    LLMCallLog,
    ProductEvent,
    utcnow,
)
from app.api.routes import essay_archive as essay_archive_routes
from app.services.essay_archive import get_version_label_for_round
from tests.conftest import create_authenticated_family, create_second_authenticated_family

_DEFAULT_SUBMITTED_AT = object()


def _add_essay_with_versions(
    session,
    *,
    student_id: str,
    essay_id: str,
    title: str = "我的作文",
    rounds: int = 1,
    submitted_at=None,
    hidden_by: str = "",
    last_version_submitted_at=_DEFAULT_SUBMITTED_AT,
    status: str = "settled",
) -> Essay:
    submitted = submitted_at or utcnow()
    archived_at = (
        submitted
        if last_version_submitted_at is _DEFAULT_SUBMITTED_AT
        else last_version_submitted_at
    )
    essay = Essay(
        id=essay_id,
        student_id=student_id,
        title=title,
        status=status,
        hidden_by=hidden_by,
        hidden_at=submitted if hidden_by else None,
        visibility_changed_at=submitted if hidden_by else None,
        last_version_submitted_at=archived_at,
    )
    session.add(essay)
    session.flush()

    for round_index in range(1, rounds + 1):
        ai_feedback = {}
        if round_index == 1:
            ai_feedback = {"revision_tasks": [{"instruction": "补一个更清楚的开头。"}]}
        elif round_index >= 2:
            ai_feedback = {"next_step": f"第 {round_index} 稿继续加细节。"}
        session.add(
            EssayVersion(
                id=f"{essay_id}-v{round_index}",
                essay_id=essay.id,
                version_label=get_version_label_for_round(round_index),
                round_index=round_index,
                content=f"{title} 第 {round_index} 稿",
                ai_feedback=ai_feedback,
                created_at=submitted + timedelta(minutes=round_index),
            )
        )

    session.commit()
    session.refresh(essay)
    return essay


def _ids(response):
    return [item["essay_id"] for item in response.json()["items"]]


def _count(session, model):
    return len(session.exec(select(model)).all())


def _as_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def test_child_archive_lists_recent_three_submitted_visible_essays(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    student_id = family["student"].id
    now = utcnow()
    for index in range(4):
        _add_essay_with_versions(
            session,
            student_id=student_id,
            essay_id=f"essay-{index}",
            title=f"作文 {index}",
            rounds=2,
            submitted_at=now + timedelta(minutes=index),
        )

    response = client.get(
        f"/api/students/{student_id}/essay-archive",
        cookies=family["cookie"],
    )

    assert response.status_code == 200
    assert _ids(response) == ["essay-3", "essay-2", "essay-1"]


def test_child_archive_excludes_prewrite_only_and_hidden_essays(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    student_id = family["student"].id
    now = utcnow()
    _add_essay_with_versions(
        session,
        student_id=student_id,
        essay_id="prewrite-only",
        rounds=0,
        last_version_submitted_at=None,
        status="prewriting",
    )
    _add_essay_with_versions(
        session,
        student_id=student_id,
        essay_id="hidden-submitted",
        rounds=1,
        hidden_by="child",
        submitted_at=now + timedelta(minutes=1),
    )
    _add_essay_with_versions(
        session,
        student_id=student_id,
        essay_id="visible-submitted",
        rounds=1,
        submitted_at=now + timedelta(minutes=2),
    )

    response = client.get(
        f"/api/students/{student_id}/essay-archive",
        cookies=family["cookie"],
    )

    assert response.status_code == 200
    assert _ids(response) == ["visible-submitted"]


def test_parent_archive_can_include_child_hidden_essays(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    student_id = family["student"].id
    _add_essay_with_versions(
        session,
        student_id=student_id,
        essay_id="hidden-submitted",
        rounds=2,
        hidden_by="child",
    )

    response = client.get(
        f"/api/parents/students/{student_id}/essay-archive?include_hidden=true",
        cookies=family["cookie"],
    )

    assert response.status_code == 200
    hidden_item = response.json()["items"][0]
    assert hidden_item["essay_id"] == "hidden-submitted"
    assert hidden_item["status"] == "hidden_by_child"


def test_parent_detail_can_return_child_hidden_essay(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    student_id = family["student"].id
    _add_essay_with_versions(
        session,
        student_id=student_id,
        essay_id="hidden-detail",
        rounds=2,
        hidden_by="child",
    )
    archive = client.get(
        f"/api/parents/students/{student_id}/essay-archive?include_hidden=true",
        cookies=family["cookie"],
    )
    essay_id = archive.json()["items"][0]["essay_id"]

    response = client.get(
        f"/api/parents/essays/{essay_id}/archive-detail",
        cookies=family["cookie"],
    )

    assert response.status_code == 200
    assert response.json()["hidden_by"] == "child"
    assert response.json()["visibility"]["hidden_by"] == "child"


def test_parent_can_restore_hidden_essay_discovered_from_archive(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    student_id = family["student"].id
    _add_essay_with_versions(
        session,
        student_id=student_id,
        essay_id="hidden-restore",
        rounds=2,
        hidden_by="child",
    )
    archive = client.get(
        f"/api/parents/students/{student_id}/essay-archive?include_hidden=true",
        cookies=family["cookie"],
    )
    essay_id = archive.json()["items"][0]["essay_id"]

    response = client.patch(
        f"/api/parents/essays/{essay_id}/visibility",
        json={"hidden": False},
        cookies=family["cookie"],
    )

    assert response.status_code == 200
    restored = response.json()
    assert restored["hidden"] is False
    assert restored["hidden_by"] == ""
    assert restored["hidden_at"] is None


def test_parent_restore_visible_essay_is_idempotent(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    changed_at = utcnow() - timedelta(days=1)
    essay = _add_essay_with_versions(
        session,
        student_id=family["student"].id,
        essay_id="already-visible-restore",
        rounds=1,
    )
    essay.visibility_changed_at = changed_at
    session.add(essay)
    session.commit()
    before_events = _count(session, ProductEvent)

    response = client.patch(
        f"/api/parents/essays/{essay.id}/visibility",
        json={"hidden": False},
        cookies=family["cookie"],
    )

    assert response.status_code == 200
    assert response.json()["hidden"] is False
    session.refresh(essay)
    assert _as_utc(essay.visibility_changed_at) == _as_utc(changed_at)
    assert _count(session, ProductEvent) == before_events


def test_child_detail_returns_404_for_hidden_essay(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    essay = _add_essay_with_versions(
        session,
        student_id=family["student"].id,
        essay_id="hidden-child-detail",
        rounds=1,
        hidden_by="child",
    )

    response = client.get(
        f"/api/essays/{essay.id}/archive-detail",
        cookies=family["cookie"],
    )

    assert response.status_code == 404


def test_archive_detail_returns_timeline_and_continue_payload(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    essay = _add_essay_with_versions(
        session,
        student_id=family["student"].id,
        essay_id="timeline-detail",
        rounds=3,
    )

    response = client.get(
        f"/api/essays/{essay.id}/archive-detail",
        cookies=family["cookie"],
    )

    assert response.status_code == 200
    payload = response.json()
    assert [version["round_index"] for version in payload["versions"]] == [1, 2, 3]
    assert payload["continue_revision"]["latest_version_id"] == "timeline-detail-v3"


def test_visibility_hide_preserves_versions_logs_history_and_events(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    student_id = family["student"].id
    essay = _add_essay_with_versions(
        session,
        student_id=student_id,
        essay_id="hide-preserves-learning",
        rounds=2,
    )
    log = LLMCallLog(
        id="hide-preserves-log",
        student_id=student_id,
        task_type=TaskType.essay,
        input_summary="作文题目：我的作文",
        validation_ok=True,
    )
    session.add(log)
    version = session.get(EssayVersion, "hide-preserves-learning-v2")
    version.llm_call_log_id = log.id
    session.add(version)
    session.add(
        AbilityHistory(
            student_id=student_id,
            ability_name="revision",
            old_value=40,
            new_value=42,
            delta=2,
            source_type=TaskType.essay,
            source_id=version.id,
        )
    )
    session.add(
        ProductEvent(
            event_type="essay_revision_feedback_completed",
            parent_id=family["parent"].id,
            student_id=student_id,
            payload={"essay_id": essay.id},
        )
    )
    session.commit()

    before = {
        EssayVersion: _count(session, EssayVersion),
        LLMCallLog: _count(session, LLMCallLog),
        AbilityHistory: _count(session, AbilityHistory),
        ProductEvent: _count(session, ProductEvent),
    }
    response = client.patch(
        f"/api/essays/{essay.id}/visibility",
        json={"hidden": True},
        cookies=family["cookie"],
    )

    assert response.status_code == 200
    assert response.json()["hidden"] is True
    assert _count(session, EssayVersion) == before[EssayVersion]
    assert _count(session, LLMCallLog) == before[LLMCallLog]
    assert _count(session, AbilityHistory) == before[AbilityHistory]
    assert _count(session, ProductEvent) == before[ProductEvent] + 1


def test_visibility_events_use_safe_actor_types(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    essay = _add_essay_with_versions(
        session,
        student_id=family["student"].id,
        essay_id="visibility-event-payload",
        rounds=1,
    )

    hide = client.patch(
        f"/api/essays/{essay.id}/visibility",
        json={"hidden": True},
        cookies=family["cookie"],
    )
    restore = client.patch(
        f"/api/parents/essays/{essay.id}/visibility",
        json={"hidden": False},
        cookies=family["cookie"],
    )

    assert hide.status_code == 200
    assert restore.status_code == 200
    events = session.exec(
        select(ProductEvent)
        .where(ProductEvent.payload["essay_id"].as_string() == essay.id)
        .order_by(ProductEvent.created_at)
    ).all()
    assert [event.event_type for event in events] == [
        "essay_hidden_by_child",
        "essay_restored_by_parent",
    ]
    assert events[0].payload["actor_type"] == "child_surface"
    assert events[1].payload["actor_type"] == "parent"
    assert "unsafe_full_content" not in events[0].payload
    assert "unsafe_full_content" not in events[1].payload


def test_visibility_request_rejects_extra_payload_keys(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    essay = _add_essay_with_versions(
        session,
        student_id=family["student"].id,
        essay_id="strict-extra-payload",
        rounds=1,
    )

    response = client.patch(
        f"/api/essays/{essay.id}/visibility",
        json={"hidden": True, "content": "孩子写的完整作文不应放在这里"},
        cookies=family["cookie"],
    )

    assert response.status_code == 422


def test_visibility_request_rejects_string_boolean(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    essay = _add_essay_with_versions(
        session,
        student_id=family["student"].id,
        essay_id="strict-string-bool",
        rounds=1,
    )

    response = client.patch(
        f"/api/essays/{essay.id}/visibility",
        json={"hidden": "true"},
        cookies=family["cookie"],
    )

    assert response.status_code == 422


def test_parent_archive_ordering_is_explicitly_nulls_last_for_postgres():
    compiled = str(
        essay_archive_routes.parent_archive_order_by()[0].compile(
            dialect=postgresql.dialect()
        )
    )

    assert "NULLS LAST" in compiled


def test_cross_family_archive_access_returns_404(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    first = create_authenticated_family(session)
    second = create_second_authenticated_family(session)
    essay = _add_essay_with_versions(
        session,
        student_id=second["student"].id,
        essay_id="other-family-essay",
        rounds=2,
        hidden_by="child",
    )

    responses = [
        client.get(
            f"/api/students/{second['student'].id}/essay-archive",
            cookies=first["cookie"],
        ),
        client.get(
            f"/api/parents/students/{second['student'].id}/essay-archive?include_hidden=true",
            cookies=first["cookie"],
        ),
        client.get(
            f"/api/essays/{essay.id}/archive-detail",
            cookies=first["cookie"],
        ),
        client.get(
            f"/api/parents/essays/{essay.id}/archive-detail",
            cookies=first["cookie"],
        ),
        client.patch(
            f"/api/essays/{essay.id}/visibility",
            json={"hidden": True},
            cookies=first["cookie"],
        ),
        client.patch(
            f"/api/parents/essays/{essay.id}/visibility",
            json={"hidden": False},
            cookies=first["cookie"],
        ),
    ]

    assert [response.status_code for response in responses] == [404, 404, 404, 404, 404, 404]
