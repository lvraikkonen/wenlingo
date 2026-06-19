from datetime import timedelta

import pytest

from app.domain.models import ParentSession, utcnow
from app.ops import cleanup_parent_sessions as cleanup_ops
from tests.conftest import create_authenticated_family


def test_cleanup_parent_sessions_command_dry_run_does_not_delete(session, monkeypatch, capsys):
    family = create_authenticated_family(session)
    parent_session = family["session"]
    parent_session.revoked_at = utcnow() - timedelta(days=45)
    parent_session_id = parent_session.id
    session.add(parent_session)
    session.commit()
    monkeypatch.setattr(cleanup_ops, "engine", session.get_bind())

    exit_code = cleanup_ops.main(["--dry-run", "--revoked-retention-days", "30"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "mode=dry-run" in captured.out
    assert "eligible_count=1" in captured.out
    assert session.get(ParentSession, parent_session_id) is not None


def test_cleanup_parent_sessions_command_execute_deletes_eligible_rows(session, monkeypatch, capsys):
    family = create_authenticated_family(session)
    parent_session = family["session"]
    parent_session.revoked_at = utcnow() - timedelta(days=45)
    parent_session_id = parent_session.id
    session.add(parent_session)
    session.commit()
    monkeypatch.setattr(cleanup_ops, "engine", session.get_bind())

    exit_code = cleanup_ops.main(["--execute", "--revoked-retention-days", "30"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "mode=execute" in captured.out
    assert "deleted_count=1" in captured.out
    assert session.get(ParentSession, parent_session_id) is None


def test_cleanup_parent_sessions_command_rejects_negative_retention():
    with pytest.raises(SystemExit):
        cleanup_ops.main(["--dry-run", "--expired-retention-days", "-1"])
