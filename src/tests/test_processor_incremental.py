"""Integration tests: CodeProcessor + DB idempotency across repeated runs."""

import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.db import CodeDB
from src.parsers.sql_lang import SqlParser
from src.processor import CodeProcessor
from src.utils import db_path_for_index_root

NESTED_PKG_MOD = """\
MODEL (
  name pkg.mod,
  kind FULL
);

WITH method AS (
  SELECT 1 AS x
)
SELECT * FROM pkg.mod
"""

NESTED_PKG_MOD_NO_REF = """\
MODEL (
  name pkg.mod,
  kind FULL
);

WITH method AS (
  SELECT 1 AS x
)
SELECT x FROM method
SELECT x FROM method
"""


def _db_counts(tmp: Path) -> dict:
    db_file = db_path_for_index_root(tmp)
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        dirs = conn.execute("SELECT id, path FROM directories ORDER BY id").fetchall()
        mod = conn.execute(
            "SELECT line_count FROM files WHERE path = ?",
            ("pkg/mod.sql",),
        ).fetchone()
        return {
            "directories": [(r["id"], r["path"]) for r in dirs],
            "files": conn.execute("SELECT COUNT(*) AS c FROM files").fetchone()["c"],
            "mod_lines": mod["line_count"],
        }
    finally:
        conn.close()


def _write_nested_fixture(tmp: Path) -> None:
    # `path_spec_for_indexing` requires a root `.gitignore` to exist.
    (tmp / ".gitignore").write_text("# test fixture\n", encoding="utf-8")
    pkg = tmp / "pkg"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "mod.sql").write_text(NESTED_PKG_MOD, encoding="utf-8")


def test_two_full_indexes_identical_counts(tmp_path: Path) -> None:
    _write_nested_fixture(tmp_path)

    db1 = CodeDB(tmp_path)
    CodeProcessor(db1, tmp_path).process(full=True)
    first = _db_counts(tmp_path)

    db2 = CodeDB(tmp_path)
    CodeProcessor(db2, tmp_path).process(full=True)
    second = _db_counts(tmp_path)

    assert first == second
    assert first["files"] >= 1
    assert first["mod_lines"] >= 1


def test_full_then_incremental_identical_counts(tmp_path: Path) -> None:
    _write_nested_fixture(tmp_path)

    db1 = CodeDB(tmp_path)
    CodeProcessor(db1, tmp_path).process(full=True)
    after_full = _db_counts(tmp_path)

    db2 = CodeDB(tmp_path)
    CodeProcessor(db2, tmp_path).process(full=False)
    after_inc = _db_counts(tmp_path)

    assert after_full == after_inc


def test_incremental_mutation_updates_counts_and_deletes(tmp_path: Path) -> None:
    _write_nested_fixture(tmp_path)

    db1 = CodeDB(tmp_path)
    CodeProcessor(db1, tmp_path).process(full=True)
    before = _db_counts(tmp_path)

    # Mutate file: remove the call and add a few lines
    mod = tmp_path / "pkg" / "mod.sql"
    mod.write_text(NESTED_PKG_MOD_NO_REF, encoding="utf-8")

    db2 = CodeDB(tmp_path)
    CodeProcessor(db2, tmp_path).process(full=True)
    after = _db_counts(tmp_path)

    assert after["files"] == before["files"]
    assert after["mod_lines"] != before["mod_lines"]


def test_extensionless_broken_symlink_is_not_a_skipped_source(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# test fixture\n", encoding="utf-8")
    (tmp_path / "mod.sql").write_text(
        "MODEL (name mod.one, kind FULL);\nSELECT 1 AS id\n",
        encoding="utf-8",
    )
    (tmp_path / "Makefile").write_text("all:\n", encoding="utf-8")
    (tmp_path / "customers").symlink_to("../packages/customers")

    db = CodeDB(tmp_path)
    processor = CodeProcessor(db, tmp_path)
    processor.process(full=True)
    names = {row["name"] for row in db.connection.execute("SELECT name FROM files")}
    assert {"mod.sql", "Makefile"} <= names
    assert "customers" not in names


def test_full_reparses_sql_and_incremental_parses_changed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def record(_self: SqlParser, _file_id: int, file_bytes: bytes) -> tuple[list[dict], list[dict]]:
        calls.append(len(file_bytes))
        return [], []

    monkeypatch.setattr(SqlParser, "parse", record)
    _write_nested_fixture(tmp_path)

    db1 = CodeDB(tmp_path)
    processor = CodeProcessor(db1, tmp_path)
    processor.process(full=True)
    assert len(calls) == 1
    assert processor.files_indexed == 1
    assert processor.files_skipped >= 1

    calls.clear()
    db2 = CodeDB(tmp_path)
    incremental = CodeProcessor(db2, tmp_path)
    incremental.process(full=False)
    assert calls == []
    assert incremental.files_indexed == 0

    calls.clear()
    db3 = CodeDB(tmp_path)
    CodeProcessor(db3, tmp_path).process(full=True)
    assert len(calls) == 1

    mod = tmp_path / "pkg" / "mod.sql"
    mod.write_text(NESTED_PKG_MOD_NO_REF, encoding="utf-8")
    future = time.time() + 10
    os.utime(mod, (future, future))
    calls.clear()
    db4 = CodeDB(tmp_path)
    CodeProcessor(db4, tmp_path).process(full=False)
    assert len(calls) == 1


def test_concurrent_run_query_does_not_raise(tmp_path: Path) -> None:
    """MCP may run tools in parallel; shared SQLite must be serialized."""
    _write_nested_fixture(tmp_path)
    db = CodeDB(tmp_path)
    processor = CodeProcessor(db, tmp_path)
    processor.process(full=True)

    def worker() -> int:
        return processor.run_query(
            lambda conn: conn.connection.execute("SELECT COUNT(*) AS c FROM files").fetchone()["c"]
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker) for _ in range(8)]
        results = [f.result() for f in as_completed(futures)]

    assert len(results) == 8
    assert all(isinstance(n, int) for n in results)
