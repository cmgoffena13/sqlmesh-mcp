"""Tests for repo-relative POSIX path normalization."""

from pathlib import Path

import pytest

from src.db import CodeDB
from src.processor import CodeProcessor
from src.sqlparse_mcp.find_importers import find_importers
from src.sqlparse_mcp.paths import normalize_repo_file_path


def test_normalize_relative_posix(tmp_path: Path) -> None:
    root = tmp_path
    assert normalize_repo_file_path("src/db.py", root) == "src/db.py"
    assert normalize_repo_file_path(r"src\db.py", root) == "src/db.py"
    assert normalize_repo_file_path("./src/db.py", root) == "src/db.py"


def test_normalize_absolute_under_root(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    abs_path = root / "pkg" / "mod.py"
    assert normalize_repo_file_path(str(abs_path), root) == "pkg/mod.py"


def test_normalize_rejects_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "other" / "x.py"
    with pytest.raises(ValueError, match="outside the workspace root"):
        normalize_repo_file_path(str(outside), root)
    with pytest.raises(ValueError, match="outside the workspace root"):
        normalize_repo_file_path("../other/x.py", root)


def test_normalize_rejects_empty(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty"):
        normalize_repo_file_path("  ", tmp_path)


def test_find_importers_notes_truncation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".gitignore").write_text("# test\n", encoding="utf-8")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "target.sql").write_text(
        "MODEL (name pkg.target, kind FULL);\nSELECT 1 AS id\n",
        encoding="utf-8",
    )
    (pkg / "a.sql").write_text(
        "MODEL (name pkg.a, kind FULL);\nSELECT * FROM pkg.target\n",
        encoding="utf-8",
    )
    (pkg / "b.sql").write_text(
        "MODEL (name pkg.b, kind FULL);\nSELECT * FROM pkg.target\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("src.sqlparse_mcp.find_importers._MAX_IMPORTER_FILES", 1)
    db = CodeDB(tmp_path)
    CodeProcessor(db, tmp_path).process()
    try:
        out = find_importers(db, "pkg/target.sql")
        assert out.startswith("Showing 1 of 2 files\n")
        assert "pkg/a.sql" in out
        assert "pkg/b.sql" not in out
    finally:
        db.close()


def test_find_importers_includes_relative_import(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# test\n", encoding="utf-8")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "sib.sql").write_text(
        "MODEL (name pkg.sib, kind FULL);\nSELECT 1 AS id\n",
        encoding="utf-8",
    )
    (pkg / "caller.sql").write_text(
        "MODEL (name pkg.caller, kind FULL);\nSELECT * FROM pkg.sib\n",
        encoding="utf-8",
    )
    db = CodeDB(tmp_path)
    CodeProcessor(db, tmp_path).process()
    try:
        out = find_importers(db, "pkg/sib.sql")
        assert "pkg/caller.sql" in out
    finally:
        db.close()


def test_find_importers_accepts_absolute_path(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# test\n", encoding="utf-8")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "target.sql").write_text(
        "MODEL (name pkg.target, kind FULL);\nSELECT 1 AS id\n",
        encoding="utf-8",
    )
    (pkg / "importer.sql").write_text(
        "MODEL (name pkg.importer, kind FULL);\nSELECT * FROM pkg.target\n",
        encoding="utf-8",
    )
    db = CodeDB(tmp_path)
    CodeProcessor(db, tmp_path).process()
    try:
        abs_target = str((tmp_path / "pkg" / "target.sql").resolve())
        out = find_importers(db, abs_target)
        assert "pkg/importer.sql" in out
        assert "Importers of" not in out
        assert "Showing" not in out
    finally:
        db.close()
