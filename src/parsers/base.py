from pydantic import BaseModel

from src.assigner import GlobalIDAssigner
from src.db import CodeDB


class ParsedSql(BaseModel):
    file_id: int
    statement_count: int
    model_names: list[str]


class ParserBase:
    def __init__(self, assigner: GlobalIDAssigner, db: CodeDB):
        self.assigner = assigner
        self.db = db

    def parse(self, file_id: int, file_bytes: bytes) -> ParsedSql:
        raise NotImplementedError
