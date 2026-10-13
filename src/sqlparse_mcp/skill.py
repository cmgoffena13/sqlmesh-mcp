import hashlib
import json
from pathlib import Path

import yaml

DESCRIPTION = (
    "Use when mapping a SQLMesh project: the largest directories by line count "
    "and the directory and file tree."
)

_SKILL_BODY = """\
IMPORTANT: Use ``get_project_overview`` and ``get_directory_tree`` for project structure.

## You need the shape of the project.
1. Use ``get_project_overview`` for the ten directories with the most lines.
2. Use ``get_directory_tree`` for the files in the repo, or pass a directory path to scope the tree.
"""


def skill_frontmatter() -> str:
    """YAML frontmatter agents can parse.

    ``DESCRIPTION`` contains ``: ``, which is illegal in an unquoted YAML
    scalar. Cursor, Claude, Codex, Gemini, Goose, Copilot, VS Code, and
    OpenCode all read this block from ``SKILL.md`` and drop the skill
    description when the block does not parse.
    """
    dumped = yaml.safe_dump(
        {"name": "sqlparse", "description": DESCRIPTION},
        sort_keys=False,
        allow_unicode=True,
    ).rstrip("\n")
    return f"---\n{dumped}\n---\n\n"


SKILL_INSTRUCTIONS = skill_frontmatter() + _SKILL_BODY


def skill_manifest(skill_bytes: bytes) -> str:
    """Skill listing served at ``skill://sqlparse/_manifest``."""
    return json.dumps(
        {
            "skill": "sqlparse",
            "description": DESCRIPTION,
            "files": [
                {
                    "path": "SKILL.md",
                    "size": len(skill_bytes),
                    "hash": f"sha256:{hashlib.sha256(skill_bytes).hexdigest()}",
                }
            ],
        },
        indent=2,
    )


def materialize_skill(base: Path) -> Path:
    """Write ``SKILL.md`` directly into ``base`` (the sqlparse config directory)."""
    base.mkdir(parents=True, exist_ok=True)
    path = base / "SKILL.md"
    path.write_text(SKILL_INSTRUCTIONS, encoding="utf-8")
    return path


def available_skill_dirs() -> list[Path]:
    """Skill directories FastMCP already knows about that exist on disk."""
    from fastmcp.server.providers.skills import (
        ClaudeSkillsProvider,
        CodexSkillsProvider,
        CopilotSkillsProvider,
        CursorSkillsProvider,
        GeminiSkillsProvider,
        GooseSkillsProvider,
        OpenCodeSkillsProvider,
        VSCodeSkillsProvider,
    )

    providers = (
        ClaudeSkillsProvider,
        CodexSkillsProvider,
        CopilotSkillsProvider,
        CursorSkillsProvider,
        GeminiSkillsProvider,
        GooseSkillsProvider,
        OpenCodeSkillsProvider,
        VSCodeSkillsProvider,
    )
    found: list[Path] = []
    seen: set[Path] = set()
    for provider_cls in providers:
        for path in provider_cls()._roots:
            if not path.is_dir():
                continue
            if path in seen:
                continue
            seen.add(path)
            found.append(path)
    return found


def sync_skill() -> list[Path]:
    """Write the sqlparse skill into FastMCP vendor skill directories that exist."""
    written: list[Path] = []
    for target in available_skill_dirs():
        skill_dir = target / "sqlparse"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(SKILL_INSTRUCTIONS, encoding="utf-8")
        written.append(skill_dir)
    if not written:
        print("No skill directories found.")
        return written
    for path in written:
        print(f"Synced skill → {path}")
    return written


def remove_skill() -> list[Path]:
    """Delete synced ``sqlparse`` skill directories."""
    import shutil

    removed: list[Path] = []
    for target in available_skill_dirs():
        skill_dir = target / "sqlparse"
        if not skill_dir.is_dir():
            continue
        shutil.rmtree(skill_dir)
        removed.append(skill_dir)
    if not removed:
        print("No sqlparse skill found.")
        return removed
    for path in removed:
        print(f"Removed skill → {path}")
    return removed
