from pathlib import Path

from src.db import CodeDB
from src.processor import CodeProcessor
from src.sqlparse_mcp.search_symbols import search_symbols

_PROD = """\
MODEL (
  name pkg.prod,
  kind FULL,
  description 'format_model for the warehouse'
);

SELECT 1 AS format_model
"""

_TRACED = """\
MODEL (
  name pkg.prod.load_rows,
  kind INCREMENTAL
);

SELECT 1 AS id
"""

_TEST = """\
MODEL (
  name tests.test_format_model,
  kind FULL,
  description 'format_model coverage'
);

SELECT 1 AS id
"""


def _index(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    pkg = root / "pkg"
    pkg.mkdir(parents=True)
    (root / ".gitignore").write_text("# test\n", encoding="utf-8")
    (pkg / "prod.sql").write_text(_PROD, encoding="utf-8")
    (pkg / "load.sql").write_text(_TRACED, encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "prod_cases.sql").write_text(_TEST, encoding="utf-8")
    db = CodeDB(root)
    CodeProcessor(db, root).process()
    db.close()
    return root


def test_search_symbols_excludes_is_test_by_default(tmp_path: Path) -> None:
    root = _index(tmp_path)
    db = CodeDB(root)
    try:
        out = search_symbols(db, "format_model", limit=20)
        assert "pkg.prod" in out
        assert "test_format_model" not in out
        assert "tests/" not in out
        assert "Legend:" not in out
        assert "Search results" not in out
        assert "pkg/prod.sql" in out
        assert "Sig:" not in out
        assert "Doc:" not in out
    finally:
        db.close()


def test_search_symbols_matches_model_kind_modifiers(tmp_path: Path) -> None:
    root = _index(tmp_path)
    db = CodeDB(root)
    try:
        rows = db.connection.execute(
            """
            SELECT s.qualified_name
            FROM symbols_fts
            INNER JOIN symbols AS s ON s.id = symbols_fts.rowid
            WHERE symbols_fts MATCH 'modifiers : INCREMENTAL*'
            """
        ).fetchall()
        assert [row["qualified_name"] for row in rows] == ["pkg.prod.load_rows"]
    finally:
        db.close()


def test_search_symbols_include_tests(tmp_path: Path) -> None:
    root = _index(tmp_path)
    db = CodeDB(root)
    try:
        out = search_symbols(db, "format_model", limit=20, include_tests=True)
        assert "pkg.prod" in out
        assert "test_format_model" in out
    finally:
        db.close()


def test_search_symbols_groups_by_file_with_rank(tmp_path: Path) -> None:
    root = _index(tmp_path)
    db = CodeDB(root)
    try:
        out = search_symbols(db, "format_model", limit=20, include_tests=True)
        hits = [line for line in out.splitlines() if line.startswith("  #")]
        assert hits
        ranks: list[int] = []
        for line in hits:
            parts = line.split()
            assert parts[0].startswith("#")
            assert parts[1] == "•"
            ranks.append(int(parts[0].removeprefix("#")))
        assert sorted(ranks) == list(range(1, len(ranks) + 1))
        name_at = [line.index(line.split()[-1]) for line in hits]
        assert len(set(name_at)) == 1
    finally:
        db.close()
