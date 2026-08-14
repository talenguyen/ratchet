import pytest

from scripts.loop_state import TaskState, next_action


def _state(**overrides) -> TaskState:
    defaults = dict(
        task_id="t1",
        contract_ref="contracts/functional/example.md",
        provider="opencode-go",
        model="qwen3.7-plus",
        rung_exhausted_at_top=False,
        attempts_at_current_rung=0,
        status="repairing",
    )
    defaults.update(overrides)
    return TaskState(**defaults)


def test_done_status_always_marks_done_regardless_of_other_fields():
    state = _state(status="done", rung_exhausted_at_top=True, attempts_at_current_rung=99)
    assert next_action(state) == "mark_done"


def test_first_repair_attempt_retries_same_rung():
    state = _state(attempts_at_current_rung=0)
    assert next_action(state) == "retry_same_rung"


def test_second_repair_attempt_raises_effort():
    state = _state(attempts_at_current_rung=1)
    assert next_action(state) == "raise_effort"


def test_third_repair_attempt_escalates_rung():
    state = _state(attempts_at_current_rung=2)
    assert next_action(state) == "escalate_rung"


def test_rung_exhausted_at_top_escalates_to_human_even_on_first_attempt():
    state = _state(attempts_at_current_rung=0, rung_exhausted_at_top=True)
    assert next_action(state) == "escalate_to_human"


def test_raises_on_status_other_than_repairing_or_done():
    state = _state(status="generating")
    with pytest.raises(ValueError):
        next_action(state)
