import shutil
from pathlib import Path

import pytest
from sqlmesh.utils.errors import ConfigError

from src.db import CodeDB
from src.processor import CodeProcessor
from src.tests.conftest import write_sqlmesh_config

_EXAMPLE = Path(__file__).resolve().parents[2] / "example"
_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_processor_dialect_comes_from_the_default_gateway(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# fixture\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        (_FIXTURES / "gateway_dialect.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    db = CodeDB(tmp_path)
    try:
        processor = CodeProcessor(db, tmp_path)
        assert processor.dialect == "postgres"
        assert processor.catalog == "memory"
    finally:
        db.close()


def test_processor_requires_a_sqlmesh_config(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# fixture\n", encoding="utf-8")
    db = CodeDB(tmp_path)
    try:
        with pytest.raises(ConfigError, match="config could not be found"):
            CodeProcessor(db, tmp_path)
    finally:
        db.close()


def test_example_project_loads_without_state_sync(tmp_path: Path) -> None:
    project = tmp_path / "example"
    shutil.copytree(_EXAMPLE, project)
    db = CodeDB(project)
    try:
        processor = CodeProcessor(db, project)
        assert processor.dialect == "duckdb"
        assert processor.catalog == "memory"
    finally:
        db.close()


def test_processor_catalog_comes_from_the_gateway_database(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# fixture\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        (_FIXTURES / "gateway_database.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    db = CodeDB(tmp_path)
    try:
        processor = CodeProcessor(db, tmp_path)
        assert processor.catalog == "warehouse"
    finally:
        db.close()


def test_write_sqlmesh_config_uses_the_duckdb_fixture(tmp_path: Path) -> None:
    write_sqlmesh_config(tmp_path)
    (tmp_path / ".gitignore").write_text("# fixture\n", encoding="utf-8")
    db = CodeDB(tmp_path)
    try:
        processor = CodeProcessor(db, tmp_path)
        assert processor.dialect == "duckdb"
        assert processor.catalog == "memory"
    finally:
        db.close()
