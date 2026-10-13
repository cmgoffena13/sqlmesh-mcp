import sys
from pathlib import Path

import pytest

# Ensure repository root is importable (so `import src.*` works)
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

collect_ignore = ["test_project"]


@pytest.fixture(autouse=True)
def _isolate_code_parse_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep index DBs under this test's tmp dir (see ``utils.get_sql_parse_config_dir``)."""
    monkeypatch.setenv(
        "SQL_PARSE_CONFIG_DIR",
        str(tmp_path / "sqlparse-config"),
    )


@pytest.fixture
def mcp_client(_isolate_code_parse_config: None):
    """In-process FastMCP client for the sqlparse server."""
    from fastmcp import Client

    from src.sqlparse_mcp import server
    from src.sqlparse_mcp.skill import materialize_skill
    from src.utils import get_sql_parse_config_dir

    # A previous test in this process may have imported the server first.
    server._SKILL_PATH = materialize_skill(get_sql_parse_config_dir())
    return Client(server.mcp)
