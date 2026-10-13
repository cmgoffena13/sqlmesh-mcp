from pathlib import Path

from src.assigner import GlobalIDAssigner
from src.db import CodeDB
from src.parsers.sql_lang import SqlParser
from src.processor import CodeProcessor
from src.tests.conftest import write_sqlmesh_config

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_EXAMPLE_MODELS = Path(__file__).resolve().parents[2] / "example" / "models"
_EXAMPLE_MODEL = _EXAMPLE_MODELS / "customer_revenue_by_day.sql"
_MODEL_QN = '"memory"."sushi"."customer_revenue_by_day"'


def test_sql_parser_reads_model_cte_columns_and_macros(tmp_path: Path) -> None:
    db = CodeDB(tmp_path)
    parser = SqlParser(GlobalIDAssigner(db), db)
    parser.catalog = "memory"
    parser.dialect = "duckdb"
    try:
        symbols, references = parser.parse(1, _EXAMPLE_MODEL.read_bytes())
        assert references == []
        by_name = {symbol["qualified_name"]: symbol for symbol in symbols}
        model = by_name[_MODEL_QN]
        assert model["kind"] == "model"
        assert model["name"] == "customer_revenue_by_day"
        assert model["docstring"] == "Table of revenue from customers by day."
        assert model["line_start"] == 2
        assert model["line_end"] == 41
        assert model["language"] == "sql"
        cte = by_name[f"{_MODEL_QN}.order_total"]
        assert cte["kind"] == "cte"
        assert cte["parent_id"] == model["id"]
        assert cte["line_start"] == 15
        customer = by_name[f"{_MODEL_QN}.customer_id"]
        assert customer["kind"] == "column"
        assert customer["parent_id"] == model["id"]
        assert customer["data_type"] == "INT"
        assert customer["docstring"] == "Customer id"
        assert customer["position_index"] == 0
        assert customer["line_start"] == 30
        country = by_name[f'{_MODEL_QN}."country code"']
        assert country["name"] == "country code"
        assert country["data_type"] is None
        assert country["docstring"] == "Customer country code, used for testing spaces"
        total = by_name[f"{_MODEL_QN}.order_total.total"]
        assert total["kind"] == "column"
        assert total["parent_id"] == cte["id"]
        assert total["data_type"] is None
        assert total["position_index"] == 1
        start_date = by_name[f"{_MODEL_QN}.start_date"]
        assert start_date["kind"] == "macro"
        assert start_date["name"] == "start_date"
        assert start_date["parent_id"] == model["id"]
        assert start_date["line_start"] == 24
        end_date = by_name[f"{_MODEL_QN}.end_date"]
        assert end_date["kind"] == "macro"
        assert end_date["line_start"] == 24
    finally:
        db.close()


def test_sql_parser_reads_a_macro_function(tmp_path: Path) -> None:
    db = CodeDB(tmp_path)
    parser = SqlParser(GlobalIDAssigner(db), db)
    parser.catalog = "memory"
    parser.dialect = "duckdb"
    try:
        symbols, _references = parser.parse(1, (_FIXTURES / "model.sql").read_bytes())
        by_name = {symbol["qualified_name"]: symbol for symbol in symbols}
        model_qn = '"memory"."pkg"."mod"'
        assert by_name[model_qn]["kind"] == "model"
        macro = by_name[f"{model_qn}.foo"]
        assert macro["kind"] == "macro"
        assert macro["name"] == "foo"
        assert macro["parent_id"] == by_name[model_qn]["id"]
        assert macro["line_start"] == 5
    finally:
        db.close()


def test_sql_parser_skips_blueprint_models(tmp_path: Path) -> None:
    db = CodeDB(tmp_path)
    parser = SqlParser(GlobalIDAssigner(db), db)
    parser.dialect = "duckdb"
    parser.catalog = "memory"
    try:
        symbols, references = parser.parse(3, (_EXAMPLE_MODELS / "blueprint.sql").read_bytes())
        assert symbols == []
        assert references == []
    finally:
        db.close()


def test_sql_parser_returns_no_symbols_when_the_model_does_not_parse(tmp_path: Path) -> None:
    db = CodeDB(tmp_path)
    parser = SqlParser(GlobalIDAssigner(db), db)
    parser.dialect = "duckdb"
    parser.catalog = "memory"
    try:
        symbols, references = parser.parse(4, (_FIXTURES / "broken.sql").read_bytes())
        assert symbols == []
        assert references == []
    finally:
        db.close()


def test_processor_stores_sql_symbols(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# fixture\n", encoding="utf-8")
    write_sqlmesh_config(tmp_path)
    (tmp_path / "mod.sql").write_text(
        (_FIXTURES / "model.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    db = CodeDB(tmp_path)
    try:
        CodeProcessor(db, tmp_path).process(full=True)
        rows = db.connection.execute(
            "SELECT kind, qualified_name FROM symbols ORDER BY qualified_name"
        ).fetchall()
        assert [(row["kind"], row["qualified_name"]) for row in rows] == [
            ("model", '"memory"."pkg"."mod"'),
            ("macro", '"memory"."pkg"."mod".foo'),
            ("column", '"memory"."pkg"."mod".id'),
            ("column", '"memory"."pkg"."mod".other'),
        ]
    finally:
        db.close()


def test_reparse_keeps_symbol_ids_and_drops_removed_macros(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# fixture\n", encoding="utf-8")
    write_sqlmesh_config(tmp_path)
    model = tmp_path / "mod.sql"
    model.write_text((_FIXTURES / "model.sql").read_text(encoding="utf-8"), encoding="utf-8")
    db = CodeDB(tmp_path)
    try:
        CodeProcessor(db, tmp_path).process(full=True)
        before = {
            row["qualified_name"]: row["id"]
            for row in db.connection.execute("SELECT id, qualified_name FROM symbols")
        }
        model.write_text(
            "MODEL (\n  name pkg.mod,\n  kind FULL\n);\nSELECT 1 AS id\n",
            encoding="utf-8",
        )
        CodeProcessor(db, tmp_path).process(full=True)
        after = {
            row["qualified_name"]: row["id"]
            for row in db.connection.execute("SELECT id, qualified_name FROM symbols")
        }
        model_qn = '"memory"."pkg"."mod"'
        assert after[model_qn] == before[model_qn]
        assert after[f"{model_qn}.id"] == before[f"{model_qn}.id"]
        assert f"{model_qn}.foo" not in after
        assert f"{model_qn}.other" not in after
    finally:
        db.close()
