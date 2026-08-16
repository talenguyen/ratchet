"""Checklist-driven task progress: tests/contracts/<slug>.progress.md IS the state.

Design spec 2026-08-16-ratchet-v3-synthesis-design.md section 3.1 (source:
ai-blueprint's "no separate snapshot format -- the checklist file IS the state"):
resuming a half-finished task means "read the checklist, find the first unchecked
line". There is no JSON snapshot to keep in sync with what actually happened; the
`- [ ]`/`- [x]` lines are the only record.

first_unchecked_step() is the resume primitive; mark_step_done() is the only writer
(the file is never edited by hand mid-task, so a step cannot be checked off without
being genuinely done).
"""
from __future__ import annotations

import re
from pathlib import Path

_UNCHECKED_RE = re.compile(r"^-\s+\[\s\]\s+(.*)$")
_CHECKED_RE = re.compile(r"^-\s+\[x\]\s+(.*)$", re.IGNORECASE)


def _steps(path: Path) -> list[tuple[bool, str]]:
    """[(checked, step_text), ...] in file order; non-checklist lines are ignored.

    Returns [] for a missing file -- a genuinely new task has no progress file yet.
    """
    if not path.exists():
        return []
    steps: list[tuple[bool, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _UNCHECKED_RE.match(line)
        if match:
            steps.append((False, match.group(1).strip()))
            continue
        match = _CHECKED_RE.match(line)
        if match:
            steps.append((True, match.group(1).strip()))
    return steps


def first_unchecked_step(path: Path) -> str | None:
    """The first `- [ ] <step>` line's text, in file order; None if every line is
    checked off or the file doesn't exist (nothing left to resume)."""
    for checked, text in _steps(path):
        if not checked:
            return text
    return None


def mark_step_done(path: Path, step: str) -> None:
    """Flip the first `- [ ] <step>` line whose text matches exactly to `- [x]`.

    Raises ValueError if no matching unchecked line exists (step already checked,
    step never listed, or file missing) -- a step that isn't on the checklist can
    never be marked done.
    """
    if not path.exists():
        raise ValueError(f"no unchecked step matching {step!r} in {path} (no such file)")
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        match = _UNCHECKED_RE.match(line)
        if match and match.group(1).strip() == step:
            lines[i] = f"- [x] {match.group(1)}"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return
    raise ValueError(f"no unchecked step matching {step!r} in {path}")
