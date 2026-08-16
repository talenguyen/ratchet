"""Brownfield adopt — old-coder's baseline rule, reimplemented clean.

For an existing codebase: `record_baseline` captures which tests ALREADY fail
before any work starts; `check_no_new_failures` later tells "a pre-existing
failure, not my problem" apart from "a regression I just caused". The line held
is zero NEW failures — pre-existing ones never block.

Failure IDs are parsed from pytest's own `-q --tb=no` summary output (one
`FAILED <test_id>` line per failing test), so fidelity comes from the real run,
not from re-implementing pytest's collection.

Stdlib only: subprocess, shlex, json, os, datetime, pathlib.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _run_and_parse_failures(project_root: Path, test_command: str) -> dict:
    """Run test_command across the whole project; return the failing test IDs.

    Appends `--tb=no` to the caller's command (e.g. "python3 -m pytest -q") so
    pytest prints one parseable `FAILED <test_id> - <reason>` line per failing
    test. Returns {"failing_ids": sorted unique list, "error": str | None}.
    """
    args = shlex.split(test_command) + ["--tb=no"]
    # PYTHONDONTWRITEBYTECODE: never load cached .pyc files (see contract.run_test).
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        result = subprocess.run(
            args, cwd=project_root, capture_output=True, text=True, env=env
        )
    except FileNotFoundError:
        return {"failing_ids": [], "error": f"command not found: {args[0]!r}"}
    combined = result.stdout + result.stderr
    failing = []
    for line in combined.splitlines():
        if line.startswith("FAILED "):
            test_id = line[len("FAILED "):].split(" - ", 1)[0].strip()
            if test_id:
                failing.append(test_id)
    return {"failing_ids": sorted(set(failing)), "error": None}


def record_baseline(project_root: Path, test_command: str, baseline_path: Path) -> dict:
    """Record which tests ALREADY fail across the whole project, before work starts.

    Runs test_command (e.g. "python3 -m pytest -q") with --tb=no appended, parses
    the FAILED lines, and writes to baseline_path:

        {"recorded_at": ISO 8601 UTC, "test_command": ..., "pre_existing_failures": [...]}

    Returns {"failures_recorded": int}. If the command cannot run, nothing is
    written and the dict carries an "error" key — a bogus empty baseline (which
    would later flag every failure as new) is worse than no baseline.
    """
    run = _run_and_parse_failures(project_root, test_command)
    if run["error"]:
        return {"failures_recorded": 0, "error": run["error"]}
    baseline = {
        "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "test_command": test_command,
        "pre_existing_failures": run["failing_ids"],
    }
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    return {"failures_recorded": len(run["failing_ids"])}


def check_no_new_failures(project_root: Path, test_command: str, baseline_path: Path) -> dict:
    """The brownfield gate: deny only on NEW failures, never pre-existing ones.

    Runs test_command again, compares the current failing test IDs against the
    recorded pre_existing_failures, and denies iff at least one current failure
    is NOT in the baseline (a genuine regression). Fixing a pre-existing failure
    is never a regression. A missing baseline denies loudly with a specific
    reason — an unrecorded project is never treated as clean.
    """
    if not baseline_path.exists():
        return {
            "decision": "deny",
            "new_failures": [],
            "reason": "no baseline recorded -- run record_baseline first",
        }
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    pre_existing = set(baseline.get("pre_existing_failures", []))
    run = _run_and_parse_failures(project_root, test_command)
    if run["error"]:
        return {
            "decision": "deny",
            "new_failures": [],
            "reason": f"test command not runnable: {run['error']}",
        }
    current = set(run["failing_ids"])
    new_failures = sorted(current - pre_existing)
    if new_failures:
        return {
            "decision": "deny",
            "new_failures": new_failures,
            "reason": f"new test failures not in baseline: {', '.join(new_failures)}",
        }
    return {
        "decision": "allow",
        "new_failures": [],
        "reason": f"no new failures ({len(current)} failing, all pre-existing)",
    }
