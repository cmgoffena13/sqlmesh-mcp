from pathlib import Path

from src.db import CodeDB
from src.processor import CodeProcessor
from src.sqlparse_mcp.project_overview import get_project_overview
from src.tests.conftest import write_sqlmesh_config

_MODEL = "MODEL (\n  name {name},\n  kind FULL\n);\nSELECT 1 AS id\n"


def _model(name: str) -> str:
    return _MODEL.format(name=name)


def test_project_overview_lists_directories_by_line_count(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# test fixture\n", encoding="utf-8")
    write_sqlmesh_config(tmp_path)
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "cli.sql").write_text(_model("pkg.cli"), encoding="utf-8")
    (pkg / "worker.sql").write_text(_model("pkg.worker"), encoding="utf-8")
    (pkg / "heavy.sql").write_text(
        "MODEL (name pkg.heavy, kind FULL);\n"
        "WITH a AS (SELECT 1 AS id), b AS (SELECT 1 AS id), "
        "c AS (SELECT 1 AS id), d AS (SELECT 1 AS id)\n"
        "SELECT * FROM a\n",
        encoding="utf-8",
    )
    other = tmp_path / "other"
    other.mkdir()
    (other / "small.sql").write_text(_model("other.small"), encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "main.sql").write_text(_model("tests.main"), encoding="utf-8")
    db = CodeDB(tmp_path)
    try:
        CodeProcessor(db, tmp_path).process()
        out = get_project_overview(db)
    finally:
        db.close()

    assert out.startswith("Directories - Top 10\n")
    assert "Entrypoints" not in out
    assert "Legend:" not in out
    pkg_line = next(line for line in out.splitlines() if line.startswith("  • pkg ("))
    other_line = next(line for line in out.splitlines() if line.startswith("  • other ("))
    assert out.index(pkg_line) < out.index(other_line)
    assert "pkg/cli.sql" not in out
    assert "tests/main.sql" not in out
    assert "pkg/worker.sql" not in out


def test_project_overview_with_only_test_files(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".gitignore").write_text("config.yaml\n", encoding="utf-8")
    write_sqlmesh_config(project)
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_one.sql").write_text("SELECT 1 AS id\n", encoding="utf-8")
    db = CodeDB(project)
    try:
        CodeProcessor(db, project).process()
        out = get_project_overview(db)
    finally:
        db.close()

    assert "No files." in out
    assert "Entrypoints" not in out
