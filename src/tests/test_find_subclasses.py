from pathlib import Path

import pytest

from src.db import CodeDB
from src.sqlparse_mcp.find_subclasses import find_subclasses


def _seed(db: CodeDB) -> None:
    db.connection.executemany(
        """
        INSERT INTO files
        (id, directory_id, name, path, normalized_path, language,
         content_hash, line_count, symbol_count, is_test)
        VALUES (?, NULL, ?, ?, ?, 'sql', 'hash', 1, 1, ?)
        """,
        [
            (1, "base.sql", "pkg/base.sql", "pkg.base", 0),
            (2, "child.sql", "pkg/child.sql", "pkg.child", 0),
            (3, "test_parent.sql", "tests/test_parent.sql", "tests.test_parent", 1),
        ],
    )
    db.connection.executemany(
        """
        INSERT INTO symbols
        (id, file_id, parent_id, name, qualified_name, kind, line_start, line_end,
         line_count, signature, docstring, modifiers, language, is_test)
        VALUES (?, ?, NULL, ?, ?, 'model', 1, 1, 1, 'MODEL ()', NULL, NULL, 'sql', ?)
        """,
        [
            (1, 1, "Parent", "pkg.base.Parent", 0),
            (2, 1, "Sibling", "pkg.base.Sibling", 0),
            (3, 1, "Alone", "pkg.base.Alone", 0),
            (4, 2, "Child", "pkg.child.Child", 0),
            (5, 2, "Grand", "pkg.child.Grand", 0),
            (6, 3, "TestChild", "tests.test_parent.TestChild", 1),
        ],
    )
    db.connection.executemany(
        "INSERT INTO symbol_bases (symbol_id, base_qualified_name) VALUES (?, ?)",
        [
            (2, "pkg.base.Parent"),
            (4, "pkg.base.Parent"),
            (5, "pkg.child.Child"),
            (6, "pkg.base.Parent"),
        ],
    )
    db.connection.commit()


@pytest.fixture
def indexed_hierarchy(tmp_path: Path) -> Path:
    db = CodeDB(tmp_path)
    _seed(db)
    db.close()
    return tmp_path


def test_find_subclasses_lists_direct_children(indexed_hierarchy: Path) -> None:
    db = CodeDB(indexed_hierarchy)
    try:
        out = find_subclasses(db, "pkg.base.Parent")
        assert "Subclasses of" not in out
        assert "Legend:" not in out
        assert "pkg/base.sql" in out
        assert "  • pkg.base.Sibling" in out
        assert "pkg/child.sql" in out
        assert "  • pkg.child.Child" in out
        assert "pkg.child.Grand" not in out
        assert "pkg.base.Alone" not in out
        assert "tests/test_parent.sql" not in out
    finally:
        db.close()


def test_find_subclasses_include_tests(indexed_hierarchy: Path) -> None:
    db = CodeDB(indexed_hierarchy)
    try:
        out = find_subclasses(db, "pkg.base.Parent", include_tests=True)
        assert "tests/test_parent.sql" in out
        assert "  • tests.test_parent.TestChild" in out
    finally:
        db.close()


def test_find_subclasses_none(indexed_hierarchy: Path) -> None:
    db = CodeDB(indexed_hierarchy)
    try:
        out = find_subclasses(db, "pkg.base.Alone")
        assert out == "No subclasses of pkg.base.Alone found."
    finally:
        db.close()


def test_find_subclasses_missing_symbol(indexed_hierarchy: Path) -> None:
    db = CodeDB(indexed_hierarchy)
    try:
        out = find_subclasses(db, "pkg.base.Missing")
        assert out == "No subclasses of pkg.base.Missing found."
    finally:
        db.close()


def test_find_subclasses_empty_input(indexed_hierarchy: Path) -> None:
    db = CodeDB(indexed_hierarchy)
    try:
        assert "non-empty qualified_name" in find_subclasses(db, "  ")
    finally:
        db.close()
