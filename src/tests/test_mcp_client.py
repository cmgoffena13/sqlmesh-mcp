"""Drive the sqlparse MCP server through FastMCP's client."""

import asyncio
import hashlib
import json
from pathlib import Path

import mcp_types
import pytest
from fastmcp import Client
from fastmcp.client.client import CallToolResult

from src.sqlparse_mcp.skill import DESCRIPTION, SKILL_INSTRUCTIONS

_PROJECT = Path(__file__).resolve().parent / "test_project"
_TOOLS = {
    "find_importers",
    "find_subclasses",
    "get_directory_tree",
    "get_file_overview",
    "get_project_overview",
    "get_symbol",
    "get_symbol_at_lines",
    "get_symbol_references",
    "search_symbols",
}


def _text(result: CallToolResult) -> str:
    assert result.is_error is False
    assert isinstance(result.data, str)
    return result.data


def _resource_text(
    contents: list[mcp_types.TextResourceContents | mcp_types.BlobResourceContents],
) -> str:
    block = contents[0]
    assert isinstance(block, mcp_types.TextResourceContents)
    return block.text


def test_client_lists_tools_and_reads_skill(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_WORKSPACE", str(_PROJECT))

    async def run() -> None:
        async with mcp_client:
            tools = await mcp_client.list_tools()
            assert {tool.name for tool in tools} == _TOOLS

            skill = _resource_text(await mcp_client.read_resource("skill://sqlparse/SKILL.md"))
            assert skill == SKILL_INSTRUCTIONS

            manifest = json.loads(
                _resource_text(await mcp_client.read_resource("skill://sqlparse/_manifest"))
            )
            digest = hashlib.sha256(SKILL_INSTRUCTIONS.encode()).hexdigest()
            assert manifest["skill"] == "sqlparse"
            assert manifest["description"] == DESCRIPTION
            assert manifest["files"] == [
                {
                    "path": "SKILL.md",
                    "size": len(SKILL_INSTRUCTIONS.encode()),
                    "hash": f"sha256:{digest}",
                }
            ]

    asyncio.run(run())


def test_client_tools_read_the_workspace(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_WORKSPACE", str(_PROJECT))

    async def run() -> None:
        async with mcp_client:
            overview = _text(await mcp_client.call_tool("get_project_overview"))
            assert overview.startswith("Directories - Top 10\n")
            assert "Legend:" not in overview
            assert "Entrypoints" not in overview
            assert "pkg (" in overview
            assert "tests/test_child.sql" not in overview

            tree = _text(await mcp_client.call_tool("get_directory_tree", {"path": "pkg"}))
            assert "child.sql" in tree
            assert "tests/test_child.sql" not in tree

            file_overview = _text(
                await mcp_client.call_tool("get_file_overview", {"file_path": "pkg/child.sql"})
            )
            assert "pkg.child" in file_overview
            assert "FROM pkg.base" in file_overview

            found = _text(
                await mcp_client.call_tool("search_symbols", {"query": "child", "limit": 5})
            )
            assert "pkg.child" in found
            assert "test_child" not in found

            context = _text(
                await mcp_client.call_tool("get_symbol", {"qualified_name": "pkg.child"})
            )
            assert "## Code Definition" not in context
            assert "name pkg.child" in context

            references = _text(
                await mcp_client.call_tool("get_symbol_references", {"qualified_name": "pkg.base"})
            )
            assert "pkg/user.sql" in references
            assert "tests/test_child.sql" not in references

            with_tests = _text(
                await mcp_client.call_tool(
                    "get_symbol_references",
                    {"qualified_name": "pkg.base", "include_tests": True},
                )
            )
            assert "tests/test_child.sql" in with_tests

            subclasses = _text(
                await mcp_client.call_tool("find_subclasses", {"qualified_name": "pkg.base"})
            )
            assert subclasses == "No subclasses of pkg.base found."

            importers = _text(
                await mcp_client.call_tool("find_importers", {"file_path": "pkg/base.sql"})
            )
            assert "pkg/child.sql" in importers
            assert "pkg/user.sql" in importers
            assert "tests/test_child.sql" not in importers

    asyncio.run(run())
