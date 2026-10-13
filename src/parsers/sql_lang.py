import sqlglot
import sqlglot.expressions as exp
from sqlglot.errors import ParseError
from sqlmesh.core.dialect import (
    MacroFunc,
    MacroVar,
    normalize_identifiers,
    normalize_model_name,
)
from sqlmesh.core.dialect import parse as parse_sqlmesh
from sqlmesh.utils.errors import SQLMeshError

from src.parsers.base import ParserBase


class SqlParser(ParserBase):
    def parse(self, file_id: int, file_bytes: bytes) -> tuple[list[dict], list[dict]]:
        text = file_bytes.decode("utf-8", errors="replace")
        self.symbols_snapshot = self.db.get_symbols_snapshot(file_id)
        symbols = self._symbols(file_id, text)
        self.db.delete_symbols(self.symbols_snapshot)
        return symbols, []

    def _symbols(self, file_id: int, text: str) -> list[dict]:
        expressions = self._expressions(text)
        model = next((expression for expression in expressions if expression.key == "model"), None)
        symbols: list[dict] = []
        if model is not None:
            query = next(
                (
                    expression
                    for expression in reversed(expressions)
                    if isinstance(expression, exp.Query)
                ),
                None,
            )
            symbols = self._model_symbols(file_id, text, model, query)
        return symbols

    def _expressions(self, text: str) -> list:
        parsed: list = []
        if self.dialect is not None:
            try:
                parsed = list(parse_sqlmesh(text, default_dialect=self.dialect))
            except (ParseError, SQLMeshError):
                parsed = []
        return parsed

    def _model_symbols(
        self,
        file_id: int,
        text: str,
        model: exp.Expr,
        query: exp.Query | None,
    ) -> list[dict]:
        name_value = self._property(model, "name")
        symbols: list[dict] = []
        if isinstance(name_value, exp.Table) and not self._is_blueprint(name_value):
            qualified = normalize_model_name(name_value, self.catalog, dialect=self.dialect)
            line_start = self._model_line_start(text)
            model_symbol = self._symbol(
                file_id=file_id,
                name=name_value.name,
                qualified_name=qualified,
                kind="model",
                line_start=line_start,
                line_end=self._max_line([model, query], fallback=line_start),
                docstring=self._docstring(model),
            )
            symbols.append(model_symbol)
            symbols.extend(self._query_symbols(file_id, model_symbol, qualified, query))
            symbols.extend(self._macro_symbols(file_id, text, model_symbol, qualified, query))
        return symbols

    def _query_symbols(
        self,
        file_id: int,
        model_symbol: dict,
        model_qn: str,
        query: exp.Query | None,
    ) -> list[dict]:
        symbols: list[dict] = []
        if query is not None:
            with_ = query.args.get("with_")
            ctes = with_.expressions if with_ is not None else []
            for cte in ctes:
                alias = cte.args["alias"].this
                cte_name = self._identifier_sql(alias)
                cte_qn = f"{model_qn}.{cte_name}"
                cte_symbol = self._symbol(
                    file_id=file_id,
                    parent_id=model_symbol["id"],
                    name=cte.alias,
                    qualified_name=cte_qn,
                    kind="cte",
                    line_start=self._line(alias, fallback=model_symbol["line_start"]),
                    line_end=self._max_line([cte], fallback=model_symbol["line_start"]),
                )
                symbols.append(cte_symbol)
                symbols.extend(
                    self._column_symbols(file_id, cte_symbol, cte_qn, cte.this.expressions)
                )
            symbols.extend(self._column_symbols(file_id, model_symbol, model_qn, query.expressions))
        return symbols

    def _column_symbols(
        self,
        file_id: int,
        parent: dict,
        parent_qn: str,
        expressions: list,
    ) -> list[dict]:
        symbols: list[dict] = []
        for index, expression in enumerate(expressions):
            alias = expression.args.get("alias")
            if alias is None:
                continue
            ident = alias.this
            name = ident.this if isinstance(ident, exp.Identifier) else expression.alias_or_name
            ident_sql = self._identifier_sql(ident)
            line = self._line(alias, fallback=self._line(ident, fallback=parent["line_start"]))
            cast = expression.find(exp.Cast)
            data_type = None
            if cast is not None and cast.args.get("to") is not None:
                data_type = cast.args["to"].sql(dialect=self.dialect)
            symbols.append(
                self._symbol(
                    file_id=file_id,
                    parent_id=parent["id"],
                    name=name,
                    qualified_name=f"{parent_qn}.{ident_sql}",
                    kind="column",
                    line_start=line,
                    line_end=line,
                    data_type=data_type,
                    position_index=index,
                    docstring=self._docstring(expression),
                )
            )
        return symbols

    def _macro_symbols(
        self,
        file_id: int,
        text: str,
        model_symbol: dict,
        model_qn: str,
        query: exp.Query | None,
    ) -> list[dict]:
        symbols: list[dict] = []
        if query is not None:
            lines = self._macro_lines(text)
            seen: set[str] = set()
            for node in query.walk():
                name = self._macro_name(node)
                if name is None or name in seen:
                    continue
                seen.add(name)
                occurrences = lines.get(name, [])
                line = occurrences[0] if occurrences else model_symbol["line_start"]
                ident_sql = self._identifier_sql(name)
                symbols.append(
                    self._symbol(
                        file_id=file_id,
                        parent_id=model_symbol["id"],
                        name=self._identifier_name(name),
                        qualified_name=f"{model_qn}.{ident_sql}",
                        kind="macro",
                        line_start=line,
                        line_end=line,
                        position_index=len(seen) - 1,
                    )
                )
        return symbols

    def _macro_name(self, node: exp.Expr) -> str | None:
        name = None
        if isinstance(node, MacroVar):
            name = str(node.name)
        elif isinstance(node, MacroFunc):
            this = node.this
            if isinstance(this, exp.Anonymous):
                name = str(this.this)
            else:
                name = str(getattr(this, "name", "")) or None
        return name

    def _macro_lines(self, text: str) -> dict[str, list[int]]:
        tokens = self._tokens(text)
        lines: dict[str, list[int]] = {}
        for index, token in enumerate(tokens):
            nxt = tokens[index + 1] if index + 1 < len(tokens) else None
            if (
                token.token_type.name == "PARAMETER"
                and nxt is not None
                and nxt.token_type.name == "VAR"
            ):
                lines.setdefault(nxt.text, []).append(token.line)
        return lines

    def _model_line_start(self, text: str) -> int:
        line = 1
        for token in self._tokens(text):
            if token.token_type.name == "VAR" and token.text.upper() == "MODEL":
                line = token.line
                break
        return line

    def _tokens(self, text: str) -> list:
        tokens: list = []
        if self.dialect is not None:
            tokenizer = sqlglot.Dialect.get_or_raise(self.dialect).tokenizer_class()
            tokens = tokenizer.tokenize(text)
        return tokens

    def _is_blueprint(self, name_value: exp.Table) -> bool:
        this = name_value.this
        return isinstance(this, MacroVar) and str(this.name) == "name"

    def _property(self, model: exp.Expr, name: str) -> exp.Expr | None:
        value = None
        for prop in model.expressions:
            if prop.name == name:
                value = prop.args.get("value")
                break
        return value

    def _identifier_sql(self, ident: exp.Expr | str) -> str:
        return self._normalized_identifier(ident).sql(dialect=self.dialect)

    def _identifier_name(self, ident: exp.Expr | str) -> str:
        return str(self._normalized_identifier(ident).this)

    def _normalized_identifier(self, ident: exp.Expr | str) -> exp.Expr:
        expression = ident if isinstance(ident, exp.Expr) else exp.to_identifier(ident)
        return normalize_identifiers(expression, dialect=self.dialect)

    def _docstring(self, node: exp.Expr) -> str | None:
        comments = getattr(node, "comments", None) or []
        text = " ".join(comment.strip() for comment in comments if str(comment).strip())
        return text or None

    def _line(self, node: exp.Expr | None, fallback: int) -> int:
        meta = getattr(node, "meta", None)
        line = meta.get("line") if isinstance(meta, dict) else None
        return line if isinstance(line, int) else fallback

    def _max_line(self, nodes: list, fallback: int) -> int:
        lines = [fallback]
        for node in nodes:
            if node is None:
                continue
            for child in node.walk():
                meta = child.meta
                if isinstance(meta, dict) and isinstance(meta.get("line"), int):
                    lines.append(meta["line"])
        return max(lines)

    def _symbol(
        self,
        *,
        file_id: int,
        name: str,
        qualified_name: str,
        kind: str,
        line_start: int,
        line_end: int,
        parent_id: int | None = None,
        data_type: str | None = None,
        position_index: int | None = None,
        docstring: str | None = None,
    ) -> dict:
        key = (qualified_name, kind)
        existing = self.symbols_snapshot.get(key)
        if existing is None:
            symbol_id = self.assigner.reserve("symbols", 1)[0]
            self.symbols_snapshot[key] = {
                "id": symbol_id,
                "line_start": line_start,
                "line_end": line_end,
                "seen": True,
            }
        else:
            existing["seen"] = True
            symbol_id = existing["id"]
        return {
            "id": symbol_id,
            "file_id": file_id,
            "parent_id": parent_id,
            "name": name,
            "qualified_name": qualified_name,
            "kind": kind,
            "line_start": line_start,
            "line_end": line_end,
            "line_count": line_end - line_start + 1,
            "data_type": data_type,
            "position_index": position_index,
            "signature": None,
            "docstring": docstring,
            "modifiers": None,
            "language": "sql",
        }
