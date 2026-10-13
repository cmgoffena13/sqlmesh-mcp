from typing import ClassVar

from src.assigner import GlobalIDAssigner
from src.db import CodeDB
from src.parsers.base import ParserBase
from src.parsers.sql_lang import SqlParser
from src.parsers.yaml_lang import YamlParser

FILE_EXTENSION_MAPPING = {
    ".sql": "sql",
    ".yaml": "yaml",
    ".yml": "yaml",
}


class ParserFactory:
    parsers: ClassVar[dict[str, type[ParserBase]]] = {
        "sql": SqlParser,
        "yaml": YamlParser,
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
