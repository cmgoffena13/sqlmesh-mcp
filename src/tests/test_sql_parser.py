from pathlib import Path

import pytest

from src.assigner import GlobalIDAssigner
from src.db import CodeDB
from src.parsers.base import ParsedSql, ParserBase
from src.parsers.factory import ParserFactory
from src.parsers.sql_lang import SqlParser

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_sql_parser_counts_statements_after_the_model_header(tmp_path: Path) -> None:
    db = CodeDB(tmp_path)
    parser = SqlParser(GlobalIDAssigner(db), db)
    try:
        parsed = parser.parse(1, (_FIXTURES / "model.sql").read_bytes())
        assert parsed == ParsedSql(file_id=1, statement_count=2, model_names=["pkg.mod"])
    finally:
        db.close()


def test_sql_parser_returns_zero_statements_when_the_query_does_not_parse(tmp_path: Path) -> None:
    db = CodeDB(tmp_path)
    parser = ParserFactory.get_parser("sql", GlobalIDAssigner(db), db)
    try:
        parsed = parser.parse(4, (_FIXTURES / "broken.sql").read_bytes())
        assert parsed.statement_count == 0
    finally:
        db.close()


def test_parser_factory_rejects_an_unknown_language(tmp_path: Path) -> None:
    db = CodeDB(tmp_path)
    try:
        with pytest.raises(ValueError, match="Unsupported Language"):
            ParserFactory.get_parser("python", GlobalIDAssigner(db), db)
    finally:
        db.close()


def test_parser_base_parse_is_not_implemented(tmp_path: Path) -> None:
    db = CodeDB(tmp_path)
    try:
        with pytest.raises(NotImplementedError):
            ParserBase(GlobalIDAssigner(db), db).parse(1, b"SELECT 1")
    finally:
        db.close()
