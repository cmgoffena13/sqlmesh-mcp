import os
from pathlib import Path

os.environ["MAX_FORK_WORKERS"] = "1"

from sqlmesh.core.context import Context


def load_sqlmesh_context(root: Path) -> Context:
    return Context(paths=root, load_state=False)
