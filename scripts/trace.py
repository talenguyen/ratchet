"""Structured per-task JSONL trace (design spec 2026-08-16-ratchet-external-standards-gaps.md
section 4.4 / plan Task 3).

Appends one JSON line per phase transition to a per-task log file. Purely additive -- for
human/tool reconstruction of a task's real timeline, never a decision input (RUNG_STATS.json
stays the aggregate that rung selection reads).

Phase values are derived from loop_state.Status itself (via typing.get_args), so the trace and
the decision procedure can never name different phases -- the state machine is the single source
of truth for what a phase is.

No new dependency: json/pathlib/datetime only, matching rung_stats.py and audit.py.
"""
from __future__ import annotations

import json
import typing
from datetime import datetime, timezone
from pathlib import Path

from scripts.loop_state import Status

_VALID_PHASES = typing.get_args(Status)


def append_event(
    trace_path: Path,
    task_id: str,
    phase: str,
    cost_usd: float | None = None,
    latency_s: float | None = None,
) -> None:
    """Append one JSON line: {"ts": iso8601, "task_id": ..., "phase": ..., "cost_usd": ...,
    "latency_s": ...}. Raises ValueError if `phase` isn't one of loop_state.Status's values -- the
    trace and the decision procedure must never name a phase the state machine doesn't have.
    """
    if phase not in _VALID_PHASES:
        raise ValueError(
            f"phase {phase!r} is not one of loop_state.Status's values {_VALID_PHASES}"
        )
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "phase": phase,
        "cost_usd": cost_usd,
        "latency_s": latency_s,
    }
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


def read_task_trace(trace_path: Path, task_id: str) -> list[dict]:
    """All events for one task_id, in file order (append-only, so already chronological)."""
    if not trace_path.exists():
        return []
    events = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event["task_id"] == task_id:
            events.append(event)
    return events
