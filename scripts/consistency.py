"""Naming-convention mining and conformance (design spec section 3.2)."""
from __future__ import annotations

import ast
import re
from pathlib import Path

_SNAKE_CASE_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def _function_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def dominant_naming_convention(paths: list[Path]) -> str:
    """Return "snake_case" if a strict majority of function names across `paths` are
    snake_case, else "unknown" -- mined from what the codebase already does, not asserted
    by a human.
    """
    names = [name for path in paths for name in _function_names(path)]
    if not names:
        return "unknown"
    snake_count = sum(1 for name in names if _SNAKE_CASE_RE.match(name))
    return "snake_case" if snake_count > len(names) / 2 else "unknown"


def nonconforming_names(paths: list[Path]) -> list[str]:
    """Function names across `paths` that don't match the mined dominant convention.

    Returns an empty list if the dominant convention is "unknown" -- there is nothing to
    conform to yet, the greenfield bootstrap case (spec section 3.1, generalized to naming).
    """
    convention = dominant_naming_convention(paths)
    if convention != "snake_case":
        return []
    return [
        name
        for path in paths
        for name in _function_names(path)
        if not _SNAKE_CASE_RE.match(name)
    ]
