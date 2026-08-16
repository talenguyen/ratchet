"""Tests for Mechanism 2: scripts/rungs.py (self-tuning cheapest-rung table).

All state files are built inside tmp_path; the real ratchet/context/models/
files in the repo are never touched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.rungs import (  # noqa: E402
    append_outcome,
    avg_cost_usd,
    load_rung_table,
    lookup_starting_rung,
    over_budget,
    pass_rate,
    retune_rung_table,
    save_rung_table,
)


def make_entry(
    task_class: str = "mechanical_edit",
    provider: str = "openai-codex",
    model: str = "gpt-5.6-luna",
    attempts: int = 12,
    passes: int = 11,
    total_cost_usd: float = 0.42,
    total_latency_s: float = 318.0,
    last_updated: str = "2026-08-16T06:54:00Z",
) -> dict:
    return {
        "task_class": task_class,
        "provider": provider,
        "model": model,
        "attempts": attempts,
        "passes": passes,
        "total_cost_usd": total_cost_usd,
        "total_latency_s": total_latency_s,
        "last_updated": last_updated,
    }


def write_table(path: Path, rungs: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rungs": rungs}, indent=2) + "\n", encoding="utf-8")
    return path


# --- load / save --------------------------------------------------------------


def test_load_save_round_trip_preserves_all_fields(tmp_path):
    table = tmp_path / "rung-table.json"
    rungs = [
        make_entry(),
        make_entry(
            task_class="integration",
            provider="anthropic",
            model="haiku-4-5",
            attempts=4,
            passes=4,
            total_cost_usd=0.2,
            total_latency_s=120.0,
            last_updated="2026-08-16T07:00:00Z",
        ),
    ]
    save_rung_table(table, rungs)
    # All fields survive; save sorts by task_class, provider, model, so the loaded
    # order is the sorted order, not the input order.
    expected = sorted(
        rungs, key=lambda e: (e["task_class"], e["provider"], e["model"])
    )
    assert load_rung_table(table) == expected
    raw = json.loads(table.read_text(encoding="utf-8"))
    assert [r["task_class"] for r in raw["rungs"]] == ["integration", "mechanical_edit"]


def test_load_rung_table_missing_file_and_no_rungs_key(tmp_path):
    assert load_rung_table(tmp_path / "nope.json") == []
    table = tmp_path / "weird.json"
    table.write_text('{"entries": []}\n', encoding="utf-8")
    assert load_rung_table(table) == []


# --- derived fields ------------------------------------------------------------


def test_derived_fields_zero_attempts_do_not_divide(tmp_path):
    entry = make_entry(attempts=0, passes=0, total_cost_usd=0.0, total_latency_s=0.0)
    assert pass_rate(entry) == 0.0
    assert avg_cost_usd(entry) == 0.0


def test_derived_fields_normal_values(tmp_path):
    entry = make_entry(attempts=12, passes=11, total_cost_usd=0.42)
    assert pass_rate(entry) == pytest.approx(11 / 12)
    assert avg_cost_usd(entry) == pytest.approx(0.42 / 12)


# --- lookup_starting_rung -------------------------------------------------------


def test_lookup_no_entry_for_task_class_returns_none(tmp_path):
    table = write_table(tmp_path / "rung-table.json", [make_entry()])
    assert lookup_starting_rung(table, "integration") is None


def test_lookup_below_min_attempts_returns_none(tmp_path):
    table = write_table(
        tmp_path / "rung-table.json", [make_entry(attempts=2, passes=2)]
    )
    assert lookup_starting_rung(table, "mechanical_edit") is None


def test_lookup_below_min_pass_rate_returns_none(tmp_path):
    table = write_table(
        tmp_path / "rung-table.json", [make_entry(attempts=10, passes=6)]  # 0.60 < 0.80
    )
    assert lookup_starting_rung(table, "mechanical_edit") is None


def test_lookup_returns_cheaper_of_two_qualifying(tmp_path):
    table = write_table(
        tmp_path / "rung-table.json",
        [
            # avg cost 0.20
            make_entry(
                provider="anthropic",
                model="haiku-4-5",
                attempts=5,
                passes=5,
                total_cost_usd=1.0,
            ),
            # avg cost 0.10 — cheaper, must win
            make_entry(
                provider="openai-codex",
                model="gpt-5.6-luna",
                attempts=5,
                passes=5,
                total_cost_usd=0.5,
            ),
        ],
    )
    got = lookup_starting_rung(table, "mechanical_edit")
    assert got is not None
    assert (got["provider"], got["model"]) == ("openai-codex", "gpt-5.6-luna")


# --- append_outcome -------------------------------------------------------------


def test_append_outcome_writes_valid_jsonl_lines(tmp_path):
    log = tmp_path / "outcomes.log.jsonl"
    append_outcome(log, "mechanical_edit", "openai-codex", "gpt-5.6-luna", "pass", 0.035, 26.5)
    append_outcome(log, "mechanical_edit", "openai-codex", "gpt-5.6-luna", "fail", 0.08, 40.0)

    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        obj = json.loads(line)
        assert set(obj) == {
            "task_class",
            "provider",
            "model",
            "result",
            "cost_usd",
            "latency_s",
            "ts",
        }
    first = json.loads(lines[0])
    assert first["result"] == "pass"
    assert first["cost_usd"] == 0.035
    assert first["latency_s"] == 26.5
    assert first["ts"].endswith("Z")  # ISO 8601 UTC


def test_append_outcome_rejects_invalid_result(tmp_path):
    log = tmp_path / "outcomes.log.jsonl"
    with pytest.raises(ValueError):
        append_outcome(log, "mechanical_edit", "openai-codex", "gpt-5.6-luna", "skip", 0.01, 1.0)
    assert not log.exists()  # validation fails before anything is written


# --- retune_rung_table -----------------------------------------------------------


def test_retune_recomputes_groups_and_is_idempotent(tmp_path):
    log = tmp_path / "outcomes.log.jsonl"
    table = tmp_path / "rung-table.json"

    # group A: mechanical_edit / openai-codex / gpt-5.6-luna — 4 outcomes, 3 pass 1 fail
    append_outcome(log, "mechanical_edit", "openai-codex", "gpt-5.6-luna", "pass", 0.010, 10.0)
    append_outcome(log, "mechanical_edit", "openai-codex", "gpt-5.6-luna", "pass", 0.020, 20.0)
    append_outcome(log, "mechanical_edit", "openai-codex", "gpt-5.6-luna", "pass", 0.030, 30.0)
    append_outcome(log, "mechanical_edit", "openai-codex", "gpt-5.6-luna", "fail", 0.040, 40.0)
    # group B: integration / anthropic / haiku-4-5 — 1 outcome, pass
    append_outcome(log, "integration", "anthropic", "haiku-4-5", "pass", 0.500, 60.0)

    retune_rung_table(table, log)
    rungs = load_rung_table(table)
    assert len(rungs) == 2

    a = next(r for r in rungs if r["task_class"] == "mechanical_edit")
    assert a["provider"] == "openai-codex" and a["model"] == "gpt-5.6-luna"
    assert a["attempts"] == 4
    assert a["passes"] == 3
    assert a["total_cost_usd"] == pytest.approx(0.10)
    assert a["total_latency_s"] == pytest.approx(100.0)
    expected_last = max(
        json.loads(line)["ts"]
        for line in log.read_text(encoding="utf-8").strip().splitlines()
        if json.loads(line)["task_class"] == "mechanical_edit"
    )
    assert a["last_updated"] == expected_last

    b = next(r for r in rungs if r["task_class"] == "integration")
    assert b["attempts"] == 1
    assert b["passes"] == 1
    assert b["total_cost_usd"] == pytest.approx(0.5)
    assert b["total_latency_s"] == pytest.approx(60.0)

    # idempotent: a second tuning run must write a byte-identical file
    before = table.read_bytes()
    retune_rung_table(table, log)
    assert table.read_bytes() == before


# --- over_budget ------------------------------------------------------------------


def test_over_budget_no_baseline_not_flagged(tmp_path):
    table = tmp_path / "rung-table.json"  # does not exist
    assert over_budget(table, "mechanical_edit", "openai-codex", "gpt-5.6-luna", 100.0, 100.0) == {
        "flagged": False,
        "reason": "no baseline yet",
    }


def test_over_budget_both_under_not_flagged(tmp_path):
    # avg cost 0.035, avg latency 26.5 -> limits 0.105 / 79.5
    table = write_table(tmp_path / "rung-table.json", [make_entry()])
    assert over_budget(table, "mechanical_edit", "openai-codex", "gpt-5.6-luna", 0.05, 30.0) == {
        "flagged": False,
        "reason": None,
    }


def test_over_budget_cost_over_flags_naming_cost(tmp_path):
    table = write_table(tmp_path / "rung-table.json", [make_entry()])
    r = over_budget(table, "mechanical_edit", "openai-codex", "gpt-5.6-luna", 1.0, 30.0)
    assert r["flagged"] is True
    assert "cost" in r["reason"]
    assert "latency" not in r["reason"]


def test_over_budget_latency_over_flags_naming_latency(tmp_path):
    table = write_table(tmp_path / "rung-table.json", [make_entry()])
    r = over_budget(table, "mechanical_edit", "openai-codex", "gpt-5.6-luna", 0.01, 200.0)
    assert r["flagged"] is True
    assert "latency" in r["reason"]
    assert "cost" not in r["reason"]


def test_over_budget_both_over_flags_naming_both(tmp_path):
    table = write_table(tmp_path / "rung-table.json", [make_entry()])
    r = over_budget(table, "mechanical_edit", "openai-codex", "gpt-5.6-luna", 1.0, 200.0)
    assert r["flagged"] is True
    assert "cost" in r["reason"]
    assert "latency" in r["reason"]
