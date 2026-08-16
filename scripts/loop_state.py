"""The generate-verify-repair loop's decision procedure (design spec section 4).

Intended budget call site (not wired here -- external-standards spec 4.3 / plan Task 2):
whichever code drives the repair loop for a live task should call `rung_stats.over_budget(...)`
on each iteration and route a `flagged: True` result through the same human-visible channel
`next_action`'s `escalate_to_human` already uses -- a signal the human sees, never a silent
abort. The checkable function ships in `rung_stats.py`; wiring it into a live call site is a
follow-up task against the pi skill / gate extension.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Status = Literal["generating", "verifying", "repairing", "stuck", "done"]


@dataclass
class TaskState:
    task_id: str
    contract_ref: str
    provider: str
    model: str
    rung_exhausted_at_top: bool
    attempts_at_current_rung: int
    status: Status
    # last phase transition, ISO8601 UTC -- written by task_state_store.save_state, so a
    # fresh session can prefer the most recently touched task when offering to resume.
    last_updated: str = ""


def next_action(state: TaskState) -> str:
    """Decide what happens next, per design spec section 4's repair order.

    Only meaningful once verification has failed and the task has moved to
    "repairing", or once it has reached "done". Order, cheapest first: retry
    once at the same rung, then raise effort on that rung, only then
    escalate the rung itself -- and escalate to a human only once the rung
    table is exhausted at the top (section 4's "stuck" condition).
    """
    if state.status == "done":
        return "mark_done"
    if state.status != "repairing":
        raise ValueError(
            f"next_action is only defined for status 'repairing' or 'done', got {state.status!r}"
        )
    if state.rung_exhausted_at_top:
        return "escalate_to_human"
    if state.attempts_at_current_rung == 0:
        return "retry_same_rung"
    if state.attempts_at_current_rung == 1:
        return "raise_effort"
    return "escalate_rung"
