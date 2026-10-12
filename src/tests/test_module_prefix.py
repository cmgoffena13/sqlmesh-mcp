from pathlib import Path

from src.db import CodeDB
from src.processor import CodeProcessor
from src.sqlparse_mcp.find_importers import find_importers


def _index(root: Path) -> CodeDB:
    (root / ".gitignore").write_text("# test\n", encoding="utf-8")
    db = CodeDB(root)
    CodeProcessor(db, root).process()
    return db


def test_models_directory_is_stripped_from_the_default_name(tmp_path: Path) -> None:
    model = tmp_path / "models" / "sushi"
    model.mkdir(parents=True)
    (model / "customers.sql").write_text(
        "SELECT 1 AS customer_id\n",
        encoding="utf-8",
    )
    db = _index(tmp_path)
    try:
        row = db.connection.execute(
            "SELECT normalized_path FROM files WHERE path = ?",
            ("models/sushi/customers.sql",),
        ).fetchone()
        assert row["normalized_path"] == "sushi.customers"
    finally:
        db.close()


def test_declared_model_name_overrides_the_path(tmp_path: Path) -> None:
    model = tmp_path / "models" / "raw"
    model.mkdir(parents=True)
    (model / "customers.sql").write_text(
        "MODEL (name sushi.customers, kind FULL);\nSELECT 1 AS customer_id\n",
        encoding="utf-8",
    )
    db = _index(tmp_path)
    try:
        row = db.connection.execute(
            "SELECT normalized_path FROM files WHERE path = ?",
            ("models/raw/customers.sql",),
        ).fetchone()
        assert row["normalized_path"] == "sushi.customers"
        symbol = db.connection.execute(
            "SELECT qualified_name, kind FROM symbols WHERE kind = 'model'"
        ).fetchone()
        assert symbol["qualified_name"] == "sushi.customers"
    finally:
        db.close()


def test_table_reference_resolves_to_the_model_file(tmp_path: Path) -> None:
    models = tmp_path / "models"
    models.mkdir()
    (models / "orders.sql").write_text(
        "MODEL (name sushi.orders, kind FULL);\nSELECT 1 AS order_id\n",
        encoding="utf-8",
    )
    (models / "customers.sql").write_text(
        "MODEL (name sushi.customers, kind FULL);\nSELECT * FROM sushi.orders\n",
        encoding="utf-8",
    )
    db = _index(tmp_path)
    try:
        row = db.connection.execute("SELECT import_path, import_type FROM imports").fetchone()
        assert row["import_type"] == "table"
        assert row["import_path"] == "sushi.orders"
        assert "models/customers.sql" in find_importers(db, "models/orders.sql")
    finally:
        db.close()


def test_path_outside_models_keeps_every_directory(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    (external / "seed.sql").write_text(
        "MODEL (name external.seed, kind SEED);\nSELECT 1 AS id\n",
        encoding="utf-8",
    )
    db = _index(tmp_path)
    try:
        row = db.connection.execute(
            "SELECT normalized_path FROM files WHERE path = ?",
            ("external/seed.sql",),
        ).fetchone()
        assert row["normalized_path"] == "external.seed"
    finally:
        db.close()
