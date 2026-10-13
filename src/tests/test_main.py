from main import EXAMPLE, main
from src.db import CodeDB


def test_main_parses_the_example_project() -> None:
    assert main() == 0
    db = CodeDB(EXAMPLE)
    try:
        row = db.connection.execute(
            "SELECT 1 FROM symbols WHERE qualified_name = ?",
            ('"memory"."sushi"."customer_revenue_by_day"',),
        ).fetchone()
        assert row is not None
    finally:
        db.close()
