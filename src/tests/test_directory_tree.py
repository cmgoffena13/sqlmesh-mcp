"""Tests for get_directory_tree MCP query."""

from pathlib import Path

from src.db import CodeDB
from src.processor import CodeProcessor
from src.sqlparse_mcp.directory_tree import get_directory_tree
from src.tests.conftest import write_sqlmesh_config


def _index(root: Path) -> None:
    (root / ".gitignore").write_text("# test fixture\n", encoding="utf-8")
    write_sqlmesh_config(root)
    pkg = root / "pkg"
    core = pkg / "core"
    core.mkdir(parents=True)
    (core / "dialect.sql").write_text(
        "MODEL (name pkg.core.dialect, kind FULL);\nSELECT 1 AS id\n",
        encoding="utf-8",
    )
    (core / "other.sql").write_text(
        "MODEL (name pkg.core.other, kind FULL);\nSELECT 1 AS id\n",
        encoding="utf-8",
    )
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_dialect.sql").write_text(
        "MODEL (name tests.test_dialect, kind FULL);\nSELECT 1 AS id\n",
        encoding="utf-8",
    )
    db = CodeDB(root)
    CodeProcessor(db, root).process()
    db.close()


def test_directory_tree_full(tmp_path: Path) -> None:
    _index(tmp_path)
    db = CodeDB(tmp_path)
    try:
        out = get_directory_tree(db)
        assert "Legend:" not in out
        assert ".\n" in out
        assert "dialect.sql" in out
        assert "test_dialect.sql" in out
    finally:
        db.close()


def test_directory_tree_path_scopes(tmp_path: Path) -> None:
    _index(tmp_path)
    db = CodeDB(tmp_path)
    try:
        out = get_directory_tree(db, path="pkg/core")
        assert "Legend:" not in out
        assert "pkg/core/" in out
        assert "dialect.sql" in out
        assert "other.sql" in out
        assert "test_dialect.sql" not in out

        pkg = get_directory_tree(db, path="pkg")
        assert "pkg/" in pkg
        assert "core/" in pkg
        assert "dialect.sql" in pkg
        assert "test_dialect.sql" not in pkg

        with_slash = get_directory_tree(db, path="pkg/core/")
        assert "dialect.sql" in with_slash
    finally:
        db.close()


def test_directory_tree_path_file_rejected(tmp_path: Path) -> None:
    _index(tmp_path)
    db = CodeDB(tmp_path)
    try:
        out = get_directory_tree(db, path="pkg/core/dialect.sql")
        assert "No directory matches" in out
    finally:
        db.close()


def test_directory_tree_path_missing(tmp_path: Path) -> None:
    _index(tmp_path)
    db = CodeDB(tmp_path)
    try:
        out = get_directory_tree(db, path="pkg/missing")
        assert "No directory matches" in out
    finally:
        db.close()
