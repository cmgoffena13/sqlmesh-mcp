from src.assigner import GlobalIDAssigner
from src.db import CodeDB


class ParserBase:
    def __init__(self, assigner: GlobalIDAssigner, db: CodeDB):
        self.assigner = assigner
        self.db = db
        self.symbols_snapshot = {}
        self.stack: list[tuple[int, str, str]] = []
        self.symbols: list[dict] = []
        self.imports: list[dict] = []
        self.symbol_references_staging: list[dict] = []

    def parse(
        self,
        file_id: int,
        file_bytes: bytes,
        module_qn: str = "",
        is_package: bool = False,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        raise NotImplementedError
