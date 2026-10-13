from pathlib import Path

from src.db import CodeDB
from src.processor import CodeProcessor

EXAMPLE = Path(__file__).resolve().parent / "example"


def main() -> int:
    if not EXAMPLE.is_dir():
        raise SystemExit(f"Missing {EXAMPLE}")
    db = CodeDB(EXAMPLE)
    try:
        db.recreate_schema()
        CodeProcessor(db, EXAMPLE).process(full=True)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
