from pathlib import Path


def test_v05c1_daily_task_limit_counter_has_migration():
    migration_path = Path(
        "app/db/migrations/versions/20260618_v05c1_daily_task_limit_counter.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert 'revision = "20260618_v05c1_daily_limit"' in migration_text
    assert 'down_revision = "20260617_v05c_ai_platform"' in migration_text
    assert "dailytasklimitcounter" in migration_text
    assert "student_id" in migration_text
    assert "task_name" in migration_text
    assert "product_day" in migration_text
    assert "reserved_count" in migration_text
    assert "consumed_count" in migration_text
    assert "active_reservations" in migration_text
    assert "reservation_expires_at" in migration_text
    assert "uq_daily_task_limit_counter_key" in migration_text
