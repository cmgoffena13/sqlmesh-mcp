from pathlib import Path

from src.db import CodeDB
from src.processor import CodeProcessor
from src.sqlparse_mcp.symbol_at_lines import get_symbol_at_lines

_TARGET = """\
MODEL (
  name pkg.target,
  kind FULL
);

WITH helper AS (
  SELECT 1 AS value
),
worker AS (
  SELECT * FROM helper
)
SELECT * FROM worker
"""


def _index(tmp_path: Path) -> Path:
    (tmp_path / ".gitignore").write_text("# test fixture\n", encoding="utf-8")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "target.sql").write_text(_TARGET, encoding="utf-8")
    db = CodeDB(tmp_path)
    CodeProcessor(db, tmp_path).process()
    db.close()
    return tmp_path


def test_symbol_at_lines_picks_the_tightest_span(tmp_path: Path) -> None:
    root = _index(tmp_path)
    db = CodeDB(root)
    try:
        assert get_symbol_at_lines(db, "pkg/target.sql", 2) == "  • pkg.target\n"
        assert get_symbol_at_lines(db, "pkg/target.sql", 7) == "  • pkg.target.helper\n"
        assert get_symbol_at_lines(db, "pkg/target.sql", 10) == "  • pkg.target.worker\n"
        assert get_symbol_at_lines(db, "pkg/target.sql", 6, 8) == "  • pkg.target.helper\n"
        assert "No symbol" in get_symbol_at_lines(db, "pkg/target.sql", 5)
    finally:
        db.close()
