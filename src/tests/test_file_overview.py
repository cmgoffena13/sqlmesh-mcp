from pathlib import Path

from src.db import CodeDB
from src.processor import CodeProcessor
from src.sqlparse_mcp.file_overview import get_file_overview

_MOD = """\
MODEL (
  name pkg.mod,
  kind FULL
);

WITH early AS (
  SELECT 1 AS value
),
late AS (
  SELECT 1 AS value
)
SELECT * FROM pkg.other
JOIN pkg.late
"""

_BOX = """\
MODEL (
  name mod.box,
  kind FULL
);

WITH size AS (
  SELECT 1 AS size
)
SELECT * FROM size
"""


def _index(tmp_path: Path) -> Path:
    (tmp_path / ".gitignore").write_text("# test fixture\n", encoding="utf-8")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.sql").write_text(_MOD, encoding="utf-8")
    (pkg / "other.sql").write_text(
        "MODEL (name pkg.other, kind FULL);\nSELECT 1 AS id\n",
        encoding="utf-8",
    )
    (pkg / "late.sql").write_text(
        "MODEL (name pkg.late, kind FULL);\nSELECT 1 AS id\n",
        encoding="utf-8",
    )
    db = CodeDB(tmp_path)
    CodeProcessor(db, tmp_path).process()
    db.close()
    return tmp_path


def test_file_overview_includes_import_and_symbol_line_numbers(tmp_path: Path) -> None:
    root = _index(tmp_path)
    db = CodeDB(root)
    try:
        out = get_file_overview(db, "pkg/mod.sql")
        assert "Legend:" not in out
        assert "Language:" not in out
        assert out.index("File:") < out.index("Total Lines:")
        assert "FROM pkg.other" in out
        assert "FROM pkg.late" in out
        assert "model  pkg.mod" in out
        assert "cte  pkg.mod.early" in out
        assert "cte  pkg.mod.late" in out
        assert "Sig:" not in out
        assert "Doc:" not in out
    finally:
        db.close()


def test_file_overview_nests_ctes_under_the_model(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# test fixture\n", encoding="utf-8")
    (tmp_path / "mod.sql").write_text(_BOX, encoding="utf-8")
    db = CodeDB(tmp_path)
    try:
        CodeProcessor(db, tmp_path).process()
        out = get_file_overview(db, "mod.sql")
        assert "model  mod.box" in out
        assert "cte  mod.box.size" in out
    finally:
        db.close()
