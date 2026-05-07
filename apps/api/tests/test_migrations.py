from pathlib import Path


def test_essay_version_unique_constraint_has_migration():
    versions_dir = Path("app/db/migrations/versions")
    migration_text = "\n".join(path.read_text(encoding="utf-8") for path in versions_dir.glob("*.py"))

    assert "uq_essay_version_label_per_essay" in migration_text
    assert "essayversion" in migration_text
    assert "essay_id" in migration_text
    assert "version_label" in migration_text
