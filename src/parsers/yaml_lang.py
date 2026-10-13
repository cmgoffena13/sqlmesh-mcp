from src.parsers.base import ParserBase


class YamlParser(ParserBase):
    def parse(self, file_id: int, file_bytes: bytes) -> tuple[list[dict], list[dict]]:
        if file_id is None:
            return [], []
        if file_bytes is None:
            return [], []
        return [], []
