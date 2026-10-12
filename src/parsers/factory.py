from typing import ClassVar

from src.assigner import GlobalIDAssigner
from src.db import CodeDB
from src.parsers.base import ParserBase
from src.parsers.sql_lang import SqlParser

FILE_EXTENSION_MAPPING = {
    ".sql": "sql",
}


class ParserFactory:
    parsers: ClassVar[dict[str, type[ParserBase]]] = {
        "sql": SqlParser,
    }

    @classmethod
    def get_parser(
        cls,
        language: str,
        assigner: GlobalIDAssigner,
        db: CodeDB,
    ) -> ParserBase:
        if language not in cls.parsers:
            raise ValueError(
                f"Unsupported Language: {language}; Supported Languages: "
                f"{', '.join(cls.parsers.keys())}"
            )
        impl = cls.parsers[language]
        return impl(assigner, db)
