import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP

from src.db import CodeDB
from src.processor import CodeProcessor
from src.sqlparse_mcp.directory_tree import get_directory_tree as run_directory_tree
from src.sqlparse_mcp.project_overview import (
    get_project_overview as run_project_overview,
)
from src.sqlparse_mcp.skill import DESCRIPTION, materialize_skill, skill_manifest
from src.utils import get_sql_parse_config_dir

_INSTRUCTIONS = """\
sqlparse tools read an up-to-date view of SQLMesh projects.
Utilize the ``sqlparse`` skill for project structure.
"""


def index_root() -> Path:
    # Claude Desktop passes workspace via env var
    workspace = os.environ.get("CLAUDE_WORKSPACE", "").strip()
    if workspace:
        return Path(workspace).resolve()
    # VS Code / Terminal passes it via CWD
    return Path.cwd().resolve()


@asynccontextmanager
async def _lifespan(_app: FastMCP) -> AsyncGenerator[dict[str, Any], None]:
    get_sql_parse_config_dir()
    root = index_root()
    db = CodeDB(root)
    processor = CodeProcessor(db, root)
    processor.process()
    try:
        yield {"db": db, "processor": processor}
    finally:
        db.close()


mcp = FastMCP("sqlparse", instructions=_INSTRUCTIONS, lifespan=_lifespan)
_SKILL_PATH = materialize_skill(get_sql_parse_config_dir())


@mcp.resource(
    "skill://sqlparse/SKILL.md",
    name="sqlparse/SKILL.md",
    description=DESCRIPTION,
    mime_type="text/markdown",
)
def sqlparse_skill() -> str:
    return _SKILL_PATH.read_text(encoding="utf-8")


@mcp.resource(
    "skill://sqlparse/_manifest",
    name="sqlparse/_manifest",
    description="File listing for sqlparse",
    mime_type="application/json",
)
def sqlparse_skill_manifest() -> str:
    return skill_manifest(_SKILL_PATH.read_bytes())


def _processor(ctx: Context) -> CodeProcessor:
    return ctx.lifespan_context["processor"]


@mcp.tool()
def get_project_overview(ctx: Context) -> str:
    """
    Return the top ten directories by line count.
    Directories are (lines L, files F).
    """
    return _processor(ctx).run_query(run_project_overview)


@mcp.tool()
def get_directory_tree(ctx: Context, path: str | None = None) -> str:
    """
    Return the repo's directory/file tree. Files are (lines L).
    Optional ``path`` scopes to one directory tree (exact path).
    """
    return _processor(ctx).run_query(lambda db: run_directory_tree(db, path=path))


def main() -> None:
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
