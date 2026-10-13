"""Shared formatting helpers for MCP tool output."""


def bullet(text: str, lead: str = "") -> str:
    """``  • text``. A ``lead`` such as ``#1 `` sits before the dot."""
    return f"  {lead}• {text}"


def file_label(name: str, line_count: int) -> str:
    """``name`` or ``name (12L)``."""
    label = name or "(unknown path)"
    stats = f" ({line_count}L)" if line_count > 0 else ""
    return f"{label}{stats}"
