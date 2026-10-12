from src.parsers.sql_lang import SqlParser


def test_model_file_parses_model_cte_and_table_refs(sql_parser: SqlParser, fixture_bytes) -> None:
    symbols, imports, references = sql_parser.parse(1, fixture_bytes("customers.sql"))
    by_name = {symbol["qualified_name"]: symbol for symbol in symbols}

    assert by_name["sushi.customers"]["kind"] == "model"
    assert by_name["sushi.customers"]["docstring"] == "customer dimension"
    assert by_name["sushi.customers"]["modifiers"] == "FULL"
    assert by_name["sushi.customers"]["signature"] == "MODEL (name sushi.customers, kind FULL)"
    assert by_name["sushi.customers.orders"]["kind"] == "cte"
    assert by_name["sushi.customers.orders"]["parent_id"] == by_name["sushi.customers"]["id"]

    import_paths = {row["import_path"] for row in imports}
    assert import_paths == {"sushi.raw_orders", "sushi.raw_customers"}
    assert "orders" not in import_paths

    referenced = {row["ref_symbol_qualified_name"] for row in references}
    assert referenced == {"sushi.raw_orders", "sushi.raw_customers"}
    assert {row["ref_kind"] for row in references} == {"access"}


def test_audit_block_is_an_audit_symbol(sql_parser: SqlParser) -> None:
    source = b"AUDIT (\n  name assert_positive_ids\n);\nSELECT * FROM sushi.orders WHERE id < 0\n"
    symbols, imports, _references = sql_parser.parse(1, source)
    assert symbols[0]["kind"] == "audit"
    assert symbols[0]["qualified_name"] == "assert_positive_ids"
    assert imports[0]["import_path"] == "sushi.orders"


def test_repeated_table_refs_keep_distinct_columns(sql_parser: SqlParser) -> None:
    source = (
        b"MODEL (name mod.run, kind FULL);\n"
        b"SELECT * FROM mod.target AS a CROSS JOIN mod.target AS b\n"
    )
    _symbols, imports, references = sql_parser.parse(1, source)
    assert len(imports) == 1
    assert len(references) == 2
    assert references[0]["source_line"] == references[1]["source_line"]
    assert references[0]["source_column"] != references[1]["source_column"]
