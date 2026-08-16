import json
import typing

import pytest

from scripts.loop_state import Status
from scripts.trace import append_event, read_task_trace


def test_append_event_with_valid_phase_writes_one_parseable_json_line(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    append_event(trace_path, "t1", "generating", cost_usd=0.01, latency_s=2.0)
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["task_id"] == "t1"
    assert event["phase"] == "generating"
    assert event["cost_usd"] == 0.01
    assert event["latency_s"] == 2.0
    assert event["ts"]


def test_append_event_invalid_phase_raises_before_writing(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    with pytest.raises(ValueError):
        append_event(trace_path, "t1", "not-a-phase")
    assert not trace_path.exists()


def test_append_event_appends_two_lines_not_overwrites(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    append_event(trace_path, "t1", "generating")
    append_event(trace_path, "t1", "verifying")
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["phase"] == "generating"
    assert json.loads(lines[1])["phase"] == "verifying"


def test_read_task_trace_filters_by_task_id_preserving_order(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    for task_id, phase in [
        ("t1", "generating"),
        ("t2", "generating"),
        ("t1", "verifying"),
        ("t2", "done"),
        ("t1", "done"),
    ]:
        append_event(trace_path, task_id, phase)
    events = read_task_trace(trace_path, "t1")
    assert [e["phase"] for e in events] == ["generating", "verifying", "done"]
    assert all(e["task_id"] == "t1" for e in events)


def test_valid_phases_are_derived_from_loop_state_status(tmp_path):
    # the trace must accept exactly the state machine's own phase names -- if Status ever
    # changes, this test fails rather than the two silently drifting apart
    trace_path = tmp_path / "trace.jsonl"
    for phase in typing.get_args(Status):
        append_event(trace_path, "t1", phase)
    phases = [json.loads(line)["phase"] for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert phases == list(typing.get_args(Status))
