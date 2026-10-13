import re

import sqlglot

from src.parsers.base import ParsedSql, ParserBase

_HEADER_RE = re.compile(r"(?is)\s*(MODEL|AUDIT)\b")
_COMMENT_LINE_RE = re.compile(r"--[^\n]*")
_JINJA_RE = re.compile(r"\{[%{].*?[%}]\}", re.DOTALL)
_MACRO_CALL_RE = re.compile(r"@[A-Za-z_][\w]*\s*\(")
_MACRO_VAR_RE = re.compile(r"@[A-Za-z_][\w]*")


class SqlParser(ParserBase):
    def parse(self, file_id: int, file_bytes: bytes) -> ParsedSql:
        text = file_bytes.decode("utf-8", errors="replace")
        expressions = _parse_expressions(_clean(_strip_header(text)))
        return ParsedSql(file_id=file_id, statement_count=len(expressions))


def _strip_header(source: str) -> str:
    body = source
    match = _HEADER_RE.match(source)
    if match is not None:
        start = source.find("(", match.end())
        end = _matching_paren(source, start) if start >= 0 else -1
        if end >= 0:
            rest = source[end + 1 :]
            if rest.lstrip().startswith(";"):
                rest = rest.lstrip()[1:]
            body = rest
    return body


def _matching_paren(source: str, start: int) -> int:
    depth = 0
    end = -1
    for index in range(start, len(source)):
        char = source[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                end = index
                break
    return end


def _clean(query: str) -> str:
    without_comments = _COMMENT_LINE_RE.sub("", query)
    without_jinja = _JINJA_RE.sub(" NULL ", without_comments)
    without_calls = _replace_macro_calls(without_jinja)
    return _MACRO_VAR_RE.sub("macro_var", without_calls)


def _replace_macro_calls(query: str) -> str:
    cursor = 0
    pieces: list[str] = []
    for match in _MACRO_CALL_RE.finditer(query):
        end = _matching_paren(query, match.end() - 1)
        if end < 0:
            continue
        pieces.append(query[cursor : match.start()])
        pieces.append("NULL")
        cursor = end + 1
    pieces.append(query[cursor:])
    return "".join(pieces)


def _parse_expressions(query: str) -> list:
    stripped = query.strip()
    expressions: list = []
    if stripped:
        try:
            expressions = [item for item in sqlglot.parse(stripped, read="duckdb") if item]
        except sqlglot.errors.ParseError:
            expressions = []
    return expressions
