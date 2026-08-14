"""Quality fitness functions (design spec section 3.2)."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

_BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.BoolOp)


def _function_complexity(node: ast.AST) -> int:
    """Cyclomatic complexity: 1 plus one per branch point inside the function.

    Note: this walks the function's full subtree, so a nested function
    definition's own branch points are counted toward both the inner and
    the outer function's score -- a known simplification, not a precise
    call-graph analysis.
    """
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, _BRANCH_NODES):
            complexity += 1
    return complexity


def cyclomatic_complexity(path: Path) -> dict[str, int]:
    """Per-function cyclomatic complexity for every function defined in `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    scores: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scores[node.name] = _function_complexity(node)
    return scores


def duplicate_line_count(paths: list[Path], min_line_length: int = 20) -> int:
    """Count of distinct lines (at least `min_line_length` chars, stripped) shared by >1 file."""
    lines_by_content: dict[str, set[str]] = {}
    import_pattern = re.compile(r'^(import\s+\S+|from\s+\S+\s+import\s+.+)$')
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if len(stripped) < min_line_length:
                continue
            if import_pattern.match(stripped):
                continue
            lines_by_content.setdefault(stripped, set()).add(str(path))
    return sum(1 for files in lines_by_content.values() if len(files) > 1)


def compute_scores(paths: list[Path]) -> dict:
    """Aggregate fitness scores across `paths`: average complexity and duplicate line count."""
    all_complexities: list[int] = []
    for path in paths:
        all_complexities.extend(cyclomatic_complexity(path).values())
    avg_complexity = sum(all_complexities) / len(all_complexities) if all_complexities else 0.0
    return {
        "avg_complexity": avg_complexity,
        "duplicate_lines": duplicate_line_count(paths),
    }


def load_baseline(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_baseline(path: Path, scores: dict) -> None:
    path.write_text(json.dumps(scores, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check_ratchet(current: dict, baseline: dict | None) -> dict:
    """A metric regresses if its current value is higher than the baseline's -- higher is
    worse for both avg_complexity and duplicate_lines. No baseline means nothing to compare
    against yet, so the check passes and the caller should save `current` as the new baseline.
    """
    if baseline is None:
        return {"passed": True, "regressions": []}
    regressions = [key for key in current if current[key] > baseline.get(key, current[key])]
    return {"passed": not regressions, "regressions": regressions}
