from pathlib import Path

from src.db import CodeDB
from src.processor import CodeProcessor


def _index(root: Path) -> CodeDB:
    (root / ".gitignore").write_text("# test\n", encoding="utf-8")
    db = CodeDB(root)
    CodeProcessor(db, root).process()
    return db


def test_normalized_path_follows_the_file_path(tmp_path: Path) -> None:
    model = tmp_path / "models" / "sushi"
    model.mkdir(parents=True)
    (model / "customers.sql").write_text(
        "MODEL (name sushi.customers, kind FULL);\nSELECT 1 AS customer_id\n",
        encoding="utf-8",
    )
    external = tmp_path / "external"
    external.mkdir()
    (external / "seed.sql").write_text(
        "MODEL (name other.seed, kind SEED);\nSELECT 1 AS id\n",
        encoding="utf-8",
    )
    db = _index(tmp_path)
    try:
        rows = {
            row["path"]: row["normalized_path"]
            for row in db.connection.execute("SELECT path, normalized_path FROM files")
        }
        assert rows["models/sushi/customers.sql"] == "models.sushi.customers"
        assert rows["external/seed.sql"] == "external.seed"
    finally:
        db.close()
