"""Repo map: largest directories by line count."""

from src.db import CodeDB
from src.sqlparse_mcp.format_utils import bullet

_TOP_DIRECTORIES = 10

_DIRECTORIES_SQL = """
SELECT
    d.path,
    COUNT(f.id) AS file_count,
    SUM(f.line_count) AS line_count
FROM files AS f
LEFT JOIN directories AS d
    ON d.id = f.directory_id
WHERE f.is_test = 0
GROUP BY d.path
HAVING SUM(f.line_count) > 0
ORDER BY line_count DESC, d.path
LIMIT ?
"""


def get_project_overview(db: CodeDB) -> str:
    """
    Top directories by line count.

    Counts use files that sit directly in each directory. Test files are skipped.
    """
    directories = list(db.connection.execute(_DIRECTORIES_SQL, (_TOP_DIRECTORIES,)).fetchall())
    lines = [
        "Directories - Top 10",
        "",
    ]
    if directories:
        for row in directories:
            line_count = int(row["line_count"])
            files = int(row["file_count"])
            lines.append(bullet(f"{row['path']} ({line_count}L, {files}F)"))
    else:
        lines.append("No files.")
    return "\n".join(lines).rstrip() + "\n"
