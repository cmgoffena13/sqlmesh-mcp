from sqlglot.errors import ParseError
from sqlmesh.core.dialect import Model
from sqlmesh.core.dialect import parse as parse_sqlmesh
from sqlmesh.utils.errors import SQLMeshError

from src.parsers.base import ParsedSql, ParserBase


class SqlParser(ParserBase):
    def parse(self, file_id: int, file_bytes: bytes) -> ParsedSql:
        expressions = _expressions(file_bytes.decode("utf-8", errors="replace"))
        return ParsedSql(
            file_id=file_id,
            statement_count=len(expressions),
            model_names=_model_names(expressions),
        )


def _expressions(sql: str) -> list:
    parsed: list = []
    try:
        parsed = list(parse_sqlmesh(sql, default_dialect="duckdb"))
    except (ParseError, SQLMeshError):
        parsed = []
    return parsed


def _model_names(expressions: list) -> list[str]:
    names: list[str] = []
    for expression in expressions:
        if isinstance(expression, Model):
            for prop in expression.expressions:
                if prop.name == "name":
                    names.append(prop.args["value"].sql(dialect="duckdb"))
    return names
