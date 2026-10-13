import sqlite3
from pathlib import Path
from typing import Any

from src.utils import db_path_for_index_root, get_sql_parse_config_dir

TABLE_BATCH_MAP = {
    "directories",
    "files",
    "symbols",
}


def index_workspace_paths() -> list[tuple[Path, Path]]:
    """``(db file, workspace path)`` for each index that recorded a root."""
    records: list[tuple[Path, Path]] = []
    for db_file in sorted(get_sql_parse_config_dir("indexes").glob("*.db")):
        connection = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        try:
            row = connection.execute("SELECT path FROM index_root WHERE id = 1").fetchone()
        except sqlite3.OperationalError:
            continue
        finally:
            connection.close()
        if row is not None and row[0]:
            records.append((db_file, Path(row[0])))
    return records


class CodeDB:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.db_file = db_path_for_index_root(self.root)
        self.connection = sqlite3.connect(str(self.db_file), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection_closed = False
        self._apply_schema()
        self._store_index_root()

    def _store_index_root(self) -> None:
        self.exec_tran(
            "INSERT OR REPLACE INTO index_root (id, path) VALUES (1, ?)",
            (str(self.root),),
        )

    def _script(self, name: str) -> None:
        path = Path(__file__).resolve().parent / name
        self.connection.executescript(path.read_text(encoding="utf-8"))

    def _apply_schema(self):
        self._script("schema.sql")

    def recreate_schema(self) -> None:
        """Drop every index table, then create them again from ``schema.sql``."""
        self._script("drop_schema.sql")
        self._apply_schema()
        self._store_index_root()

    def exec_tran(self, query: str, params: tuple) -> None:
        try:
            self.connection.execute(query, params)
            self.connection.commit()
        except sqlite3.Error:
            self.connection.rollback()
            raise

    def delete_ids(self, table: str, ids: list[int]) -> None:
        if not ids:
            return
        if table not in TABLE_BATCH_MAP:
            raise ValueError(f"unsupported table for delete_ids: {table}")
        placeholders = ",".join(["?"] * len(ids))
        query = f"DELETE FROM {table} WHERE id IN ({placeholders})"  # noqa: S608
        self.exec_tran(query, tuple(ids))

    def table_max_id(self, table: str) -> int:
        q = f"SELECT COALESCE(MAX(id), 0) AS max_id FROM {table}"  # noqa: S608
        return int(self.connection.execute(q).fetchone()["max_id"])

    def get_watermark(self) -> tuple[int, int]:
        row = self.connection.execute(
            "SELECT last_full_parse, last_incremental FROM watermarks WHERE id = 1"
        ).fetchone()
        return row["last_full_parse"], row["last_incremental"]

    def set_watermark(self, last_full_parse: int | None, last_incremental: int) -> None:
        if last_full_parse is not None:
            query = "UPDATE watermarks SET last_full_parse = ?, last_incremental = ? WHERE id = 1"
            params = (last_full_parse, last_incremental)
        else:
            query = "UPDATE watermarks SET last_incremental = ? WHERE id = 1"
            params = (last_incremental,)
        self.exec_tran(query, params)

    def get_directories_snapshot(self) -> dict[Path, dict[str, Any]]:
        cursor = self.connection.execute("SELECT id, path FROM directories")
        return {Path(row["path"]): {"id": row["id"], "seen": False} for row in cursor}

    def delete_directories(self, directories: dict[Path, dict[str, Any]]) -> None:
        dir_ids = [d["id"] for d in directories.values() if not d["seen"]]
        self.delete_ids("directories", dir_ids)

    def get_files_snapshot(self) -> dict[Path, dict[str, Any]]:
        cursor = self.connection.execute(
            """
            SELECT id, directory_id, path, content_hash, line_count, symbol_count, is_test
            FROM files
            """
        )
        return {
            Path(row["path"]): {
                "id": row["id"],
                "directory_id": row["directory_id"],
                "seen": False,
                "content_hash": row["content_hash"],
                "line_count": row["line_count"],
                "symbol_count": row["symbol_count"],
                "is_test": bool(row["is_test"]),
            }
            for row in cursor
        }

    def delete_files(self, files: dict[Path, dict[str, Any]]) -> None:
        file_ids = [file["id"] for file in files.values() if not file["seen"]]
        self.delete_symbols_for_files(file_ids)
        self.delete_ids("files", file_ids)

    def delete_symbols_for_files(self, file_ids: list[int]) -> None:
        if not file_ids:
            return
        placeholders = ",".join(["?"] * len(file_ids))
        self.exec_tran(
            f"DELETE FROM symbols WHERE file_id IN ({placeholders})",  # noqa: S608
            tuple(file_ids),
        )

    def bulk_insert(self, db_batches: dict[str, list[dict[str, Any]]]) -> None:
        directories = db_batches["directories"]
        files = db_batches["files"]
        with self.connection:
            self.connection.executemany(
                """
                INSERT INTO directories
                (id, parent_id, name, path, depth)
                VALUES (:id, :parent_id, :name, :path, :depth)
                """,
                directories,
            )

            self.connection.executemany(
                """
                INSERT OR REPLACE INTO files
                (id, directory_id, name, path, normalized_path, language,
                 content_hash, line_count, symbol_count, is_test)
                VALUES (:id, :directory_id, :name, :path, :normalized_path,
                        :language, :content_hash, :line_count, :symbol_count,
                        :is_test)
                """,
                files,
            )

            self.connection.executemany(
                """
                INSERT OR REPLACE INTO symbols
                (id, file_id, parent_id, name, qualified_name, kind, line_start,
                 line_end, line_count, data_type, position_index, signature, 
                 docstring, modifiers, language)
                VALUES (:id, :file_id, :parent_id, :name, :qualified_name, :kind,
                        :line_start, :line_end, :line_count, :data_type, :position_index,
                        :signature, :docstring, :modifiers, :language)
                """,
                db_batches["symbols"],
            )

    def close(self):
        if not self.connection_closed:
            self.connection.close()
            self.connection_closed = True

    def __del__(self):
        if not getattr(self, "connection_closed", True):
            conn = getattr(self, "connection", None)
            if conn is not None:
                conn.close()
            self.connection_closed = True
