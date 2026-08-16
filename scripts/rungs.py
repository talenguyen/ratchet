"""Mechanism 2, reimplemented clean against ratchet-v2's own formats.

Self-tuning cheapest-rung table: for each task class, which (provider, model)
is cheap enough to dispatch to — decided from measured outcomes, never guessed.

State (formats documented in ratchet/context/models/README.md):
- rung-table.json     {"rungs": [...]}  -- a tuned projection of the log
- outcomes.log.jsonl  append-only per-step outcome records (one JSON object per
  line: task_class, provider, model, result, cost_usd, latency_s, ts)

The tuning step (`retune_rung_table`) recomputes the table from scratch every
time, reading the whole log — the table is never an independent record. Because
every field is derived purely from the log (including last_updated, taken as
the group's newest outcome ts), tuning is idempotent: same log in, byte-identical
rung-table.json out.

Stdlib only: json, datetime, pathlib.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_OUTCOME_FIELDS = (
    "task_class",
    "provider",
    "model",
    "result",
    "cost_usd",
    "latency_s",
    "ts",
)
_VALID_RESULTS = ("pass", "fail")


def load_rung_table(path: Path) -> list[dict]:
    """Read rung-table.json; return the list under the top-level "rungs" key
    (empty list if the file doesn't exist or has no such key)."""
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("rungs", [])


def save_rung_table(path: Path, rungs: list[dict]) -> None:
    """Write back as {"rungs": [...]}, entries sorted by task_class, then
    provider, then model, for stable diffs."""
    ordered = sorted(
        rungs,
        key=lambda e: (
            e.get("task_class", ""),
            e.get("provider", ""),
            e.get("model", ""),
        ),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rungs": ordered}, indent=2) + "\n", encoding="utf-8")


def pass_rate(entry: dict) -> float:
    """Derived field: passes / attempts. 0.0 when attempts is 0 (JSON cannot
    compute it; the README documents it as computed, never stored)."""
    attempts = entry.get("attempts", 0) or 0
    if attempts == 0:
        return 0.0
    return (entry.get("passes", 0) or 0) / attempts


def avg_cost_usd(entry: dict) -> float:
    """Derived field: total_cost_usd / attempts. 0.0 when attempts is 0."""
    attempts = entry.get("attempts", 0) or 0
    if attempts == 0:
        return 0.0
    return (entry.get("total_cost_usd", 0.0) or 0.0) / attempts


def _avg_latency_s(entry: dict) -> float:
    """Derived field used by over_budget: total_latency_s / attempts."""
    attempts = entry.get("attempts", 0) or 0
    if attempts == 0:
        return 0.0
    return (entry.get("total_latency_s", 0.0) or 0.0) / attempts


def lookup_starting_rung(
    rung_table_path: Path,
    task_class: str,
    min_pass_rate: float = 0.8,
    min_attempts: int = 3,
) -> dict | None:
    """Cheapest qualifying rung for a task class, or None.

    Qualifying = attempts >= min_attempts AND measured pass_rate >= min_pass_rate.
    Cheapest = lowest avg_cost_usd. Returns None when nothing qualifies — a cold
    start must not fabricate a ranking; the caller picks manually.
    """
    candidates = [
        e
        for e in load_rung_table(rung_table_path)
        if e.get("task_class") == task_class
        and (e.get("attempts", 0) or 0) >= min_attempts
        and pass_rate(e) >= min_pass_rate
    ]
    if not candidates:
        return None
    return min(candidates, key=avg_cost_usd)


def append_outcome(
    outcomes_log_path: Path,
    task_class: str,
    provider: str,
    model: str,
    result: str,
    cost_usd: float,
    latency_s: float,
) -> None:
    """Append one JSON line to outcomes.log.jsonl, exactly per the documented
    format: task_class, provider, model, result, cost_usd, latency_s, ts
    (ISO 8601 UTC). result must be "pass" or "fail"; anything else raises
    ValueError and nothing is written."""
    if result not in _VALID_RESULTS:
        raise ValueError(f"invalid result {result!r}: must be 'pass' or 'fail'")
    line = json.dumps(
        {
            "task_class": task_class,
            "provider": provider,
            "model": model,
            "result": result,
            "cost_usd": cost_usd,
            "latency_s": latency_s,
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    outcomes_log_path.parent.mkdir(parents=True, exist_ok=True)
    with outcomes_log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def retune_rung_table(rung_table_path: Path, outcomes_log_path: Path) -> None:
    """THE self-tuning step: recompute rung-table.json from the outcome log.

    Reads every line of outcomes.log.jsonl, groups by (task_class, provider,
    model), and recomputes attempts/passes/total_cost_usd/total_latency_s from
    scratch — the table is a tuned projection of the log, not an independent
    record. last_updated is the group's newest outcome ts (the log fully
    determines the file, which is what makes this idempotent). Malformed or
    invalid lines raise ValueError loudly rather than silently diverging the
    projection from the log.
    """
    if not outcomes_log_path.exists():
        entries: list[dict] = []
    else:
        groups: dict[tuple[str, str, str], dict] = {}
        for lineno, line in enumerate(
            outcomes_log_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                outcome = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"malformed outcome at {outcomes_log_path}:{lineno}: {exc}"
                ) from exc
            if not isinstance(outcome, dict) or any(
                outcome.get(field) is None for field in _OUTCOME_FIELDS
            ):
                raise ValueError(
                    f"outcome at {outcomes_log_path}:{lineno} is missing a required "
                    f"field (need {', '.join(_OUTCOME_FIELDS)})"
                )
            if outcome["result"] not in _VALID_RESULTS:
                raise ValueError(
                    f"outcome at {outcomes_log_path}:{lineno} has invalid result "
                    f"{outcome['result']!r}: must be 'pass' or 'fail'"
                )
            key = (outcome["task_class"], outcome["provider"], outcome["model"])
            group = groups.setdefault(
                key,
                {
                    "task_class": outcome["task_class"],
                    "provider": outcome["provider"],
                    "model": outcome["model"],
                    "attempts": 0,
                    "passes": 0,
                    "total_cost_usd": 0.0,
                    "total_latency_s": 0.0,
                    "last_updated": "",
                },
            )
            group["attempts"] += 1
            group["passes"] += 1 if outcome["result"] == "pass" else 0
            group["total_cost_usd"] += outcome["cost_usd"]
            group["total_latency_s"] += outcome["latency_s"]
            # All ts values are written by append_outcome in one consistent
            # "%Y-%m-%dT%H:%M:%SZ" format, so max() is a valid newest-first pick.
            group["last_updated"] = max(group["last_updated"], outcome["ts"])
        entries = list(groups.values())
    save_rung_table(rung_table_path, entries)


def over_budget(
    rung_table_path: Path,
    task_class: str,
    provider: str,
    model: str,
    current_cost_usd: float,
    current_latency_s: float,
    cost_multiplier: float = 3.0,
    latency_multiplier: float = 3.0,
) -> dict:
    """Flag an in-progress step whose cost/latency exceeds the multiplier times
    the matching rung's own historical average. No recorded entry for this
    (task_class, provider, model) -> {"flagged": False, "reason": "no baseline
    yet"}: cold start must not block. Otherwise the reason names which of cost
    and/or latency is over."""
    entry = next(
        (
            e
            for e in load_rung_table(rung_table_path)
            if e.get("task_class") == task_class
            and e.get("provider") == provider
            and e.get("model") == model
        ),
        None,
    )
    if entry is None:
        return {"flagged": False, "reason": "no baseline yet"}
    cost_limit = cost_multiplier * avg_cost_usd(entry)
    latency_limit = latency_multiplier * _avg_latency_s(entry)
    over_cost = current_cost_usd > cost_limit
    over_latency = current_latency_s > latency_limit
    if over_cost and over_latency:
        return {
            "flagged": True,
            "reason": (
                f"cost {current_cost_usd:.4f} exceeds {cost_multiplier:g}x rung average "
                f"{cost_limit:.4f} and latency {current_latency_s:.2f}s exceeds "
                f"{latency_multiplier:g}x rung average {latency_limit:.2f}s"
            ),
        }
    if over_cost:
        return {
            "flagged": True,
            "reason": (
                f"cost {current_cost_usd:.4f} exceeds {cost_multiplier:g}x rung average "
                f"{cost_limit:.4f}"
            ),
        }
    if over_latency:
        return {
            "flagged": True,
            "reason": (
                f"latency {current_latency_s:.2f}s exceeds {latency_multiplier:g}x rung "
                f"average {latency_limit:.2f}s"
            ),
        }
    return {"flagged": False, "reason": None}
