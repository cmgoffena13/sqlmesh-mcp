from pathlib import Path

from src.db import CodeDB
from src.processor import CodeProcessor
from src.sqlparse_mcp.symbol_context import get_symbol_context
from src.sqlparse_mcp.symbol_references import get_symbol_references

_TARGET = """\
MODEL (
  name pkg.target.helper,
  kind FULL
);

SELECT 1 AS value
"""

_USER = """\
MODEL (
  name pkg.user.run,
  kind FULL
);

SELECT * FROM pkg.target.helper
UNION ALL
SELECT * FROM pkg.target.helper
"""

_TEST = """\
MODEL (
  name tests.test_helper,
  kind FULL
);

SELECT * FROM pkg.target.helper
"""


def _index(tmp_path: Path) -> Path:
    (tmp_path / ".gitignore").write_text("# test fixture\n", encoding="utf-8")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "target.sql").write_text(_TARGET, encoding="utf-8")
    (pkg / "user.sql").write_text(_USER, encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_target.sql").write_text(_TEST, encoding="utf-8")
    db = CodeDB(tmp_path)
    CodeProcessor(db, tmp_path).process()
    db.close()
    return tmp_path


def test_symbol_context_definition_only(tmp_path: Path) -> None:
    root = _index(tmp_path)
    db = CodeDB(root)
    try:
        out = get_symbol_context(db, "pkg.target.helper")
        assert "## Code Definition" not in out
        assert "Legend:" not in out
        assert "Kind:" not in out
        assert "Lines:" not in out
        assert "## References (3)" in out
        assert "Access: 3" in out
        assert "Calls:" not in out
        assert "Type Annotations:" not in out
        assert "Parent:" not in out
        assert "Language:" not in out
        assert "Symbol:" not in out
        assert out.index("File:") < out.index("name pkg.target.helper")
        assert "pkg/user.sql" not in out
        assert "tests/test_target.sql" not in out
        assert "## Calls" not in out
    finally:
        db.close()


def test_symbol_references_lists_accesses_with_counts(tmp_path: Path) -> None:
    root = _index(tmp_path)
    db = CodeDB(root)
    try:
        out = get_symbol_references(db, "pkg.target.helper")
        assert "References of" not in out
        assert "Legend:" not in out
        assert "total" not in out
        assert "pkg/user.sql" in out
        assert "tests/test_target.sql" not in out
        assert "## Access" in out
        assert "  • L" in out
        assert "pkg.user.run" in out
        assert "pkg/user.sql:" not in out
        assert "(" in out
    finally:
        db.close()


def test_symbol_references_include_tests(tmp_path: Path) -> None:
    root = _index(tmp_path)
    db = CodeDB(root)
    try:
        out = get_symbol_references(db, "pkg.target.helper", include_tests=True)
        assert "pkg/user.sql" in out
        assert "tests/test_target.sql" in out
    finally:
        db.close()


def test_symbol_references_none(tmp_path: Path) -> None:
    root = _index(tmp_path)
    db = CodeDB(root)
    try:
        out = get_symbol_references(db, "pkg.target.missing")
        assert out == "No references to pkg.target.missing were found."
    finally:
        db.close()
