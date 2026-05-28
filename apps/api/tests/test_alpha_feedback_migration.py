from pathlib import Path


def test_alpha_feedback_observation_has_migration():
    migration_path = Path(
        "app/db/migrations/versions/20260527_alpha_feedback_observation.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "20260527_alpha_feedback_observation" in migration_text
    assert 'down_revision = "20260521_assessment_artifacts"' in migration_text
    assert "alphainvitecode" in migration_text
    assert "productevent" in migration_text
    assert "feedbackreaction" in migration_text
    assert "parentfeedback" in migration_text
    assert "uq_feedbackreaction_student_target" in migration_text
    assert "uq_parentfeedback_parent_student_target" in migration_text
    assert "ix_productevent_event_type" in migration_text
    assert "ix_productevent_parent_id" in migration_text
    assert "ix_productevent_student_id" in migration_text
    assert "ix_productevent_invite_code_id" in migration_text
