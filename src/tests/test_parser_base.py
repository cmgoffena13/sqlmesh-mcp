from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.db import CodeDB
from src.parsers.base import ParserBase


def test_parser_base_parse_not_implemented(tmp_path: Path) -> None:
    db = CodeDB(tmp_path)
    base = ParserBase(MagicMock(), db)
    with pytest.raises(NotImplementedError):
        base.parse(1, b"")
    db.close()
