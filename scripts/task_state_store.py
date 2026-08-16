"""Discover resumable tasks from checklist state: tests/contracts/<slug>.progress.md.

Design spec 2026-08-16-ratchet-v3-synthesis-design.md section 3.1: no separate JSON
snapshot -- the checklist file IS the state. A fresh session's resume check is "read
the checklist, find the first unchecked line"; `resumable_tasks()` is the discovery
step that finds which checklists still have an unchecked line before reading them.

The old `.ratchet/state/<task_id>.json` snapshot (foundational-gaps spec Task 2) is
gone: it duplicated state a plain checklist file already represents and drifted out of
sync with what actually happened. `loop_state.TaskState`/`next_action` still exist for
the repair decision ladder, but task_state_store no longer persists them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from scripts.progress import first_unchecked_step
except ImportError:
    from progress import first_unchecked_step

_PROGRESS_GLOB = "*.progress.md"
_PROGRESS_SUFFIX = ".progress.md"


def _slug_from_path(path: Path) -> str:
    """tests/contracts/<slug>.progress.md -> <slug> (e.g. demo.progress.md -> demo)."""
    return path.name[: -len(_PROGRESS_SUFFIX)]


def resumable_tasks(project_root: Path) -> list[dict]:
    """Every tests/contracts/<slug>.progress.md whose first step is still unchecked --
    what a fresh session should be shown before starting anything, so it can offer to
    resume rather than silently starting a second, colliding attempt at the same work.

    Returns [{"slug", "progress_path", "next_step"}, ...], sorted by slug. A checklist
    whose lines are all checked is a finished task and is not resumable.
    """
    contracts_dir = project_root / "tests" / "contracts"
    if not contracts_dir.exists():
        return []
    tasks = []
    for path in sorted(contracts_dir.glob(_PROGRESS_GLOB)):
        next_step = first_unchecked_step(path)
        if next_step is not None:
            tasks.append(
                {
                    "slug": _slug_from_path(path),
                    "progress_path": str(path.relative_to(project_root)),
                    "next_step": next_step,
                }
            )
    return tasks


def main(argv: list[str]) -> int:
    usage = (
        "usage: task_state_store.py resumable <project_root>\n"
        "       task_state_store.py next-step <progress.md path>"
    )
    if len(argv) < 3:
        print(json.dumps({"error": usage}))
        return 2

    command, arg = argv[1], Path(argv[2])
    rest = argv[3:]

    if command == "resumable" and len(rest) == 0:
        tasks = resumable_tasks(arg)
        print(json.dumps({"tasks": tasks}, indent=2))
        return 0

    if command == "next-step" and len(rest) == 0:
        print(json.dumps({"progress_path": str(arg), "next_step": first_unchecked_step(arg)}))
        return 0

    print(json.dumps({"error": usage}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
