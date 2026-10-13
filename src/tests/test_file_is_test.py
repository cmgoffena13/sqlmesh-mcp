from pathlib import Path

from src.db import CodeDB
from src.processor import CodeProcessor, file_path_is_test
from src.tests.conftest import write_sqlmesh_config


def test_file_path_is_test_rules() -> None:
    assert file_path_is_test(Path("tests/core/test_foo.sql"))
    assert file_path_is_test(Path("test_foo.sql"))
    assert file_path_is_test(Path("pkg/foo_test.sql"))
    assert file_path_is_test(Path("tests/helpers.sql"))
    assert not file_path_is_test(Path("models/test/definition.sql"))
    assert not file_path_is_test(Path("models/dbt/test.sql"))
    assert not file_path_is_test(Path("models/core/customers.sql"))


def test_file_is_test_not_promoted_from_symbol_names(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# fixture\n", encoding="utf-8")
    write_sqlmesh_config(tmp_path)
    models = tmp_path / "models" / "test"
    models.mkdir(parents=True)
    (models / "definition.sql").write_text(
        "MODEL (name test.definition, kind FULL);\nSELECT 1 AS test_run\n",
        encoding="utf-8",
    )
    (tmp_path / "models" / "dbt").mkdir()
    (tmp_path / "models" / "dbt" / "test.sql").write_text(
        "MODEL (name dbt.test, kind FULL);\nSELECT 1 AS id\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_real.sql").write_text(
        "MODEL (name tests.test_real, kind FULL);\nSELECT 1 AS ok\n",
        encoding="utf-8",
    )

    db = CodeDB(tmp_path)
    try:
        CodeProcessor(db, tmp_path).process()
        rows = {
            row["path"]: bool(row["is_test"])
            for row in db.connection.execute("SELECT path, is_test FROM files")
        }
        assert rows["models/test/definition.sql"] is False
        assert rows["models/dbt/test.sql"] is False
        assert rows["tests/test_real.sql"] is True
    finally:
        db.close()
