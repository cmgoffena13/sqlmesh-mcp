import re

import sqlglot
from sqlglot import exp

from src.assigner import GlobalIDAssigner
from src.db import CodeDB
from src.parsers.base import ParserBase
from src.parsers.parser_utils import StackFrame

_BLOCK_KINDS = ("MODEL", "AUDIT")
_NAME_RE = re.compile(r"(?im)^\s*name\s+([A-Za-z_][\w.]*)")
_KIND_RE = re.compile(r"(?im)^\s*kind\s+([A-Za-z_][\w]*)")
_DESCRIPTION_RE = re.compile(r"(?is)\bdescription\s+(?:'([^']*)'|\"([^\"]*)\")")
_COMMENT_LINE_RE = re.compile(r"--[^\n]*")
_JINJA_RE = re.compile(r"\{[%{].*?[%}]\}", re.DOTALL)
_MACRO_CALL_RE = re.compile(r"@[A-Za-z_][\w]*\s*\(")
_MACRO_VAR_RE = re.compile(r"@[A-Za-z_][\w]*")


class SqlParser(ParserBase):
    def __init__(self, assigner: GlobalIDAssigner, db: CodeDB):
        self.assigner = assigner
        self.db = db
        self.stack: list[StackFrame] = []
        self.symbols: list[dict] = []
        self.imports: list[dict] = []
        self.symbol_references: list[dict] = []
        self.symbols_snapshot = {}
        self.symbols_references_snapshot = {}
        self.imports_snapshot = {}
        self._module_qn = ""
        self._source = ""

    def parse(
        self,
        file_id: int,
        file_bytes: bytes,
        module_qn: str = "",
        is_package: bool = False,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        del is_package
        self.stack = []
        self._module_qn = module_qn
        self.symbols = []
        self.imports = []
        self.symbol_references = []
        self._source = file_bytes.decode("utf-8", errors="replace")
        self._query_prefix = 0
        self.symbols_snapshot = self.db.get_symbols_snapshot(file_id)
        self.symbols_references_snapshot = self.db.get_symbol_references_snapshot(file_id)
        self.imports_snapshot = self.db.get_imports_snapshot(file_id)
        self._parse_source(file_id)
        self.db.delete_symbol_references(self.symbols_references_snapshot)
        self.db.delete_symbols(self.symbols_snapshot)
        self.db.delete_imports(self.imports_snapshot)
        return self.symbols, self.imports, self.symbol_references

    def _parse_source(self, file_id: int) -> None:
        block = _leading_block(self._source)
        query = self._source
        parent_id = None
        if block is not None:
            kind, body, query, line_start, line_end = block
            parent_id = self._emit_block(file_id, kind, body, line_start, line_end)
        self._query_prefix = len(self._source) - len(query)
        self._parse_query(file_id, query, parent_id)

    def _emit_block(
        self,
        file_id: int,
        kind: str,
        body: str,
        line_start: int,
        line_end: int,
    ) -> int:
        props = _properties(body)
        qualified = props.get("name") or self._module_qn or kind.lower()
        name = qualified.rsplit(".", 1)[-1]
        symbol_kind = "model" if kind == "MODEL" else "audit"
        signature = _signature(kind, qualified, props.get("kind"))
        symbol_id = self._add_symbol(
            file_id=file_id,
            name=name,
            qualified_name=qualified,
            kind=symbol_kind,
            line_start=line_start,
            line_end=line_end,
            signature=signature,
            docstring=props.get("description"),
            modifiers=props.get("kind"),
            parent_id=None,
        )
        self.stack.append(StackFrame(symbol_id, qualified, symbol_kind, False))
        return symbol_id

    def _parse_query(self, file_id: int, query: str, parent_id: int | None) -> None:
        cleaned = _sqlglot_text(query)
        expressions = _parse_expressions(cleaned)
        cte_names = _cte_names(expressions)
        for expression in expressions:
            for cte in expression.find_all(exp.CTE):
                self._emit_cte(file_id, cte, parent_id)
        seen_tables: set[str] = set()
        seen_imports: set[str] = set()
        for expression in expressions:
            for table in expression.find_all(exp.Table):
                qualified = _table_qualified_name(table)
                if not qualified or qualified in seen_tables or _is_cte_reference(table, cte_names):
                    continue
                seen_tables.add(qualified)
                self._emit_table(file_id, qualified, parent_id, seen_imports)

    def _emit_cte(self, file_id: int, cte: exp.CTE, parent_id: int | None) -> None:
        alias = cte.alias
        if not alias:
            return
        parent_qn = self.stack[-1].qualified_name if self.stack else self._module_qn
        qualified = f"{parent_qn}.{alias}" if parent_qn else alias
        line_start, line_end = _cte_span(self._source, alias)
        self._add_symbol(
            file_id=file_id,
            name=alias,
            qualified_name=qualified,
            kind="cte",
            line_start=line_start,
            line_end=line_end,
            signature=f"{alias} AS (...)",
            docstring=None,
            modifiers=None,
            parent_id=parent_id,
        )

    def _emit_table(
        self,
        file_id: int,
        qualified: str,
        parent_id: int | None,
        seen_imports: set[str],
    ) -> None:
        occurrences = _occurrences(self._source, qualified, self._query_prefix)
        if not occurrences:
            occurrences = [(1, 0)]
        if qualified not in seen_imports:
            seen_imports.add(qualified)
            line_number, _column = occurrences[0]
            self._add_import(file_id, qualified, line_number)
        for line_number, column in occurrences:
            self._add_reference(file_id, qualified, parent_id, line_number, column)

    def _add_symbol(
        self,
        file_id: int,
        name: str,
        qualified_name: str,
        kind: str,
        line_start: int,
        line_end: int,
        signature: str,
        docstring: str | None,
        modifiers: str | None,
        parent_id: int | None,
    ) -> int:
        symbol_id = self.assigner.reserve("symbols", 1)[0]
        self.symbols.append(
            {
                "id": symbol_id,
                "file_id": file_id,
                "parent_id": parent_id,
                "name": name,
                "qualified_name": qualified_name,
                "kind": kind,
                "line_start": line_start,
                "line_end": line_end,
                "line_count": line_end - line_start + 1,
                "signature": signature,
                "docstring": docstring,
                "modifiers": modifiers,
                "language": "sql",
                "base_qualified_names": [],
                "is_test": False,
            }
        )
        return symbol_id

    def _add_import(self, file_id: int, qualified: str, line_number: int) -> None:
        key = (qualified, "")
        stored = self.imports_snapshot.get(key)
        changed = stored is None or stored["line_number"] != line_number
        import_id = self.assigner.reserve("imports", 1)[0] if stored is None else stored["id"]
        if stored is None:
            self.imports_snapshot[key] = {
                "id": import_id,
                "line_number": line_number,
                "seen": True,
            }
        else:
            stored["seen"] = True
            stored["line_number"] = line_number
        if changed:
            self.imports.append(
                {
                    "id": import_id,
                    "file_id": file_id,
                    "import_path": qualified,
                    "imported_symbol": "",
                    "alias": None,
                    "line_number": line_number,
                    "import_type": "table",
                    "import_scope": "file",
                    "signature": f"FROM {qualified}",
                }
            )

    def _add_reference(
        self,
        file_id: int,
        qualified: str,
        source_symbol_id: int | None,
        line_number: int,
        column: int,
    ) -> None:
        reference_id = self.assigner.reserve("symbol_references", 1)[0]
        name = qualified.rsplit(".", 1)[-1]
        self.symbol_references.append(
            {
                "id": reference_id,
                "ref_symbol_name": name,
                "ref_symbol_qualified_name": qualified,
                "source_file_id": file_id,
                "source_symbol_id": source_symbol_id,
                "source_line": line_number,
                "source_column": column,
                "ref_kind": "access",
                "context": f"FROM {qualified}",
            }
        )


def _leading_block(source: str) -> tuple[str, str, str, int, int] | None:
    stripped = source.lstrip()
    offset = len(source) - len(stripped)
    kind = ""
    upper = stripped.upper()
    for candidate in _BLOCK_KINDS:
        if upper.startswith(candidate) and (
            len(stripped) == len(candidate) or not stripped[len(candidate)].isalnum()
        ):
            kind = candidate
    result = None
    if kind:
        open_at = stripped.find("(", len(kind))
        if open_at != -1:
            close_at = _matching_paren(stripped, open_at)
            if close_at is not None:
                body = stripped[open_at + 1 : close_at]
                rest_start = close_at + 1
                if rest_start < len(stripped) and stripped[rest_start] == ";":
                    rest_start += 1
                absolute_close = offset + close_at
                line_start = source.count("\n", 0, offset) + 1
                line_end = source.count("\n", 0, absolute_close) + 1
                result = (kind, body, stripped[rest_start:], line_start, line_end)
    return result


def _matching_paren(text: str, open_at: int) -> int | None:
    depth = 0
    index = open_at
    close_at = None
    while index < len(text) and close_at is None:
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                close_at = index
        index += 1
    return close_at


def _properties(body: str) -> dict[str, str]:
    props: dict[str, str] = {}
    name_match = _NAME_RE.search(body)
    kind_match = _KIND_RE.search(body)
    description_match = _DESCRIPTION_RE.search(body)
    if name_match:
        props["name"] = name_match.group(1)
    if kind_match:
        props["kind"] = kind_match.group(1)
    if description_match:
        props["description"] = description_match.group(1) or description_match.group(2) or ""
    return props


def _signature(kind: str, name: str, model_kind: str | None) -> str:
    parts = [f"name {name}"]
    if model_kind:
        parts.append(f"kind {model_kind}")
    return f"{kind} ({', '.join(parts)})"


def _sqlglot_text(query: str) -> str:
    without_comments = _COMMENT_LINE_RE.sub("", query)
    without_jinja = _JINJA_RE.sub(" ", without_comments)
    without_calls = _replace_macro_calls(without_jinja)
    return _MACRO_VAR_RE.sub("macro_var", without_calls)


def _replace_macro_calls(text: str) -> str:
    result = text
    match = _MACRO_CALL_RE.search(result)
    while match:
        open_at = result.find("(", match.start())
        close_at = _matching_paren(result, open_at) if open_at != -1 else None
        if close_at is None:
            result = result[: match.start()] + "NULL" + result[match.end() :]
        else:
            result = result[: match.start()] + "NULL" + result[close_at + 1 :]
        match = _MACRO_CALL_RE.search(result)
    return result


def _parse_expressions(query: str) -> list:
    parsed = []
    stripped = query.strip()
    if stripped:
        try:
            parsed = [
                expression for expression in sqlglot.parse(stripped, read="duckdb") if expression
            ]
        except sqlglot.errors.ParseError:
            parsed = []
    return parsed


def _cte_names(expressions: list) -> set[str]:
    names: set[str] = set()
    for expression in expressions:
        for cte in expression.find_all(exp.CTE):
            if cte.alias:
                names.add(cte.alias)
    return names


def _table_qualified_name(table: exp.Table) -> str:
    parts = [part for part in (table.catalog, table.db, table.name) if part]
    return ".".join(parts)


def _is_cte_reference(table: exp.Table, cte_names: set[str]) -> bool:
    return not table.db and not table.catalog and table.name in cte_names


def _cte_span(source: str, alias: str) -> tuple[int, int]:
    match = re.search(rf"(?im)(?<!\w){re.escape(alias)}\s+AS\s*\(", source)
    line_start = 1
    line_end = 1
    if match:
        line_start = source.count("\n", 0, match.start()) + 1
        open_at = source.find("(", match.start())
        close_at = _matching_paren(source, open_at) if open_at != -1 else None
        end = close_at if close_at is not None else match.end()
        line_end = source.count("\n", 0, end) + 1
    return line_start, line_end


def _occurrences(source: str, qualified: str, prefix: int) -> list[tuple[int, int]]:
    pattern = re.compile(rf"(?<![\w.]){re.escape(qualified)}(?![\w])")
    found: list[tuple[int, int]] = []
    for match in pattern.finditer(source, prefix):
        line = source.count("\n", 0, match.start()) + 1
        line_start = source.rfind("\n", 0, match.start()) + 1
        column = match.start() - line_start
        found.append((line, column))
    return found
