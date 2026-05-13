import os
import sqlite3
import subprocess
import sys


def test_init_db_module_creates_domain_tables(tmp_path):
    db_path = tmp_path / "init.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

    result = subprocess.run(
        [sys.executable, "-m", "app.db.init_db"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type = 'table'"
            )
        }

    assert {"parentuser", "studentprofile"}.issubset(tables)
