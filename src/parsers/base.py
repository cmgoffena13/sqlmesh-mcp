from src.assigner import GlobalIDAssigner
from src.db import CodeDB


class ParserBase:
    def __init__(self, assigner: GlobalIDAssigner, db: CodeDB):
        self.assigner = assigner
        self.db = db

    def parse(self, file_id: int, file_bytes: bytes) -> tuple[list[dict], list[dict]]:
        raise NotImplementedError
