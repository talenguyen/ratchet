"""Mechanism 1, reimplemented clean against Ratchet's own contract format.

Mechanically-enforced red-before-green contracts with a tamper-evident sha256
sidecar, at the two structural seams of the loop (see AGENTS.md):

- propose -> implement boundary: `propose_contract` (the contract test must be
  FAILING right now, else nothing is written), `approve_contract` (records the
  hash sidecar + approval stamp after re-checking the test is still red),
  `can_implement` (blocked unless approved and untampered).
- complete gate: `verify_complete` (untampered AND green, with distinct denial
  reasons for tamper / removed file / still failing).

State lives in ratchet/contracts/<work-item-id>/contract.json; the contract test
file itself is an ordinary pytest file (path recorded in the contract). The
sha256 recorded at approval time is the sidecar every gate re-checks, so a test
edited after approval cannot silently pass.

Stdlib only: hashlib, json, os, subprocess, datetime, pathlib.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# pytest's own exit codes, kept distinguishable on purpose:
# 0 = pass, 1 = fail, 5 = no tests collected, 4 = usage error, 2/3 = internal errors.
_NO_TESTS_COLLECTED = 5
_TAIL_CHARS = 4000


def sha256_of(path: Path) -> str:
    """Hex sha256 of a file's bytes — the tamper-evident primitive."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_test(project_root: Path, test_file_path: str) -> dict:
    """Run `python3 -m pytest -q <test_file_path>` from project_root.

    Returns {"returncode": int, "tail": str}, where tail is the last ~4000 chars
    of combined stdout+stderr. Returncode 5 (no tests collected) is kept
    distinguishable from 0 (pass) and 1 (fail).
    """
    # PYTHONDONTWRITEBYTECODE: never load cached .pyc files — a same-size rewrite
    # within the same second can otherwise execute stale bytecode. Env, not a CLI
    # flag, so the specified command shape stays exactly as documented.
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", "-q", test_file_path],
            cwd=project_root,
            capture_output=True,
            text=True,
            env=env,
        )
    except FileNotFoundError:
        return {
            "returncode": 127,
            "tail": "pytest run failed: python3 not found or cwd does not exist",
        }
    combined = (result.stdout + result.stderr)[-_TAIL_CHARS:]
    return {"returncode": result.returncode, "tail": combined}


def contract_path(project_root: Path, work_item_id: str) -> Path:
    """Where the contract state for a work item lives."""
    return project_root / "ratchet" / "contracts" / work_item_id / "contract.json"


def _load_contract(project_root: Path, work_item_id: str) -> dict | None:
    path = contract_path(project_root, work_item_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_contract(project_root: Path, work_item_id: str, contract: dict) -> None:
    dest = contract_path(project_root, work_item_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")


def propose_contract(project_root: Path, work_item_id: str, test_file_path: str) -> dict:
    """RED-BEFORE-GREEN enforcement point, propose half.

    Allows only when the contract test currently FAILS (returncode 1). On allow,
    writes ratchet/contracts/<id>/contract.json recording the test file's sha256
    right now plus the captured failure as fail-mode evidence, with no approval
    stamp yet. On any deny, writes nothing.
    """
    result = run_test(project_root, test_file_path)

    if result["returncode"] == 0:
        return {
            "decision": "deny",
            "reason": (
                f"{test_file_path} already passes against the current code -- "
                "cannot distinguish done from not-done, make it fail first"
            ),
        }
    if result["returncode"] == _NO_TESTS_COLLECTED:
        return {
            "decision": "deny",
            "reason": f"{test_file_path} collected no tests -- nothing to be done against",
        }
    if result["returncode"] != 1:
        return {
            "decision": "deny",
            "reason": f"pytest error (exit {result['returncode']}): {result['tail']}",
        }

    contract = {
        "work_item_id": work_item_id,
        "test_file_path": test_file_path,
        "test_file_sha256": sha256_of(project_root / test_file_path),
        "fail_mode_evidence": result["tail"],
        "approved_by": None,
        "approved_at": None,
        "kind": "new_work",
    }
    _write_contract(project_root, work_item_id, contract)
    return {
        "decision": "allow",
        "reason": f"contract proposed for {work_item_id}: test currently FAILS as required",
    }


def characterize_contract(project_root: Path, work_item_id: str, test_file_path: str) -> dict:
    """Inverse of propose_contract: capture EXISTING behavior as a regression guard.

    A characterization test asserts current, already-true behavior, so it must
    currently PASS to be a valid capture — a failing characterization test is a
    wrong capture (a typo in the recorded value), not real behavior. Denies with
    a distinct reason when the test fails or collects no tests.

    On allow, writes the same contract.json shape propose_contract uses, plus
    "kind": "characterization" (propose_contract writes "kind": "new_work").
    fail_mode_evidence holds the passing run's output — the evidence of what was
    captured. No approval stamp yet: same stop-for-review discipline as propose.
    """
    result = run_test(project_root, test_file_path)

    if result["returncode"] == _NO_TESTS_COLLECTED:
        return {
            "decision": "deny",
            "reason": (
                f"{test_file_path} collected no tests -- nothing captured to characterize"
            ),
        }
    if result["returncode"] == 1:
        return {
            "decision": "deny",
            "reason": (
                f"{test_file_path} FAILS against the current code -- a characterization "
                "test that fails is a wrong capture; re-run the target and record what "
                "it actually returns, not what you assumed:\n"
                f"{result['tail']}"
            ),
        }
    if result["returncode"] != 0:
        return {
            "decision": "deny",
            "reason": f"pytest error (exit {result['returncode']}): {result['tail']}",
        }

    contract = {
        "work_item_id": work_item_id,
        "test_file_path": test_file_path,
        "test_file_sha256": sha256_of(project_root / test_file_path),
        "fail_mode_evidence": result["tail"],
        "approved_by": None,
        "approved_at": None,
        "kind": "characterization",
    }
    _write_contract(project_root, work_item_id, contract)
    return {
        "decision": "allow",
        "reason": (
            f"contract characterized for {work_item_id}: test currently PASSES as required"
        ),
    }


def approve_contract(project_root: Path, work_item_id: str, approved_by: str) -> dict:
    """Approve half of the propose->implement boundary.

    Reads the proposed contract, re-verifies the on-disk test file still hashes
    to the recorded sidecar (no drift since propose), then re-runs the test with
    the expectation set by the contract's kind:

    - "new_work" (default if the key is absent, for backward compat): the test
      must STILL be failing right now — someone implementing before approval
      defeats the point of red-before-green.
    - "characterization": the test must STILL be passing right now — a
      characterization capture records already-true behavior, so a capture that
      now fails means the behavior drifted or the capture was wrong.

    On allow, stamps approved_by / approved_at (ISO 8601 UTC) and reports which
    state was required ("still failing"/"still passing, as required").
    """
    contract = _load_contract(project_root, work_item_id)
    if contract is None:
        return {
            "decision": "deny",
            "reason": f"no proposed contract for {work_item_id}, run propose first",
        }

    test_file_path = contract.get("test_file_path")
    recorded_hash = contract.get("test_file_sha256")
    if not test_file_path or not recorded_hash:
        return {
            "decision": "deny",
            "reason": (
                f"malformed contract for {work_item_id}: "
                "missing test_file_path or test_file_sha256"
            ),
        }

    try:
        current_hash = sha256_of(project_root / test_file_path)
    except FileNotFoundError:
        current_hash = None
    if current_hash != recorded_hash:
        return {
            "decision": "deny",
            "reason": "test file changed since propose -- re-propose",
        }

    result = run_test(project_root, test_file_path)
    if result["returncode"] == _NO_TESTS_COLLECTED:
        return {
            "decision": "deny",
            "reason": "test collected no tests during approval -- re-propose",
        }
    if result["returncode"] not in (0, 1):
        return {
            "decision": "deny",
            "reason": f"pytest error (exit {result['returncode']}): {result['tail']}",
        }

    # The re-check's expectation is set by the contract's kind: new-work contracts
    # must still be FAILING at approval (red-before-green); characterization
    # contracts capture already-true behavior and must still be PASSING at
    # approval, or the captured behavior has drifted.
    kind = contract.get("kind", "new_work")
    if kind == "characterization":
        if result["returncode"] != 0:
            return {
                "decision": "deny",
                "reason": (
                    "characterization capture no longer passes before approval -- the "
                    "recorded behavior drifted or the capture is wrong; re-propose"
                ),
            }
        expected_state = "still passing, as required"
    else:
        if result["returncode"] != 1:
            return {
                "decision": "deny",
                "reason": (
                    "test now passes before approval -- the work was implemented early, "
                    "which defeats the point of a red-before-green contract; re-propose"
                ),
            }
        expected_state = "still failing, as required"

    contract["approved_by"] = approved_by
    contract["approved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_contract(project_root, work_item_id, contract)
    return {
        "decision": "allow",
        "reason": f"approved contract for {work_item_id} ({expected_state})",
    }


def can_implement(project_root: Path, work_item_id: str) -> dict:
    """The propose->implement gate.

    implement is blocked unless the contract exists, is actually approved
    (approved_by not null — proposed is not enough), and the on-disk test file
    still matches the recorded sha256 sidecar.
    """
    contract = _load_contract(project_root, work_item_id)
    if contract is None:
        return {
            "allowed": False,
            "reason": f"no contract for {work_item_id} -- run propose first",
        }
    if contract.get("approved_by") is None:
        return {
            "allowed": False,
            "reason": (
                f"contract for {work_item_id} is proposed but not approved "
                "(approved_by is null) -- run approve first"
            ),
        }

    test_file_path = contract.get("test_file_path")
    recorded_hash = contract.get("test_file_sha256")
    if not test_file_path or not recorded_hash:
        return {
            "allowed": False,
            "reason": f"malformed contract for {work_item_id}: missing test_file_path or test_file_sha256",
        }
    try:
        current_hash = sha256_of(project_root / test_file_path)
    except FileNotFoundError:
        current_hash = None
    if current_hash != recorded_hash:
        return {"allowed": False, "reason": "contract file changed since approval"}

    return {
        "allowed": True,
        "reason": f"contract for {work_item_id} is approved and untampered",
    }


def verify_complete(project_root: Path, work_item_id: str) -> dict:
    """The complete gate — Mechanism 1's second enforcement seam.

    Denies unless the contract exists, the on-disk test file is byte-for-byte
    unchanged since approval (tamper check first, so a doctored green test is
    caught), and the test now PASSES. Three distinct denial reasons: hash
    mismatch (tampered) / test file removed / still failing.
    """
    contract = _load_contract(project_root, work_item_id)
    if contract is None:
        return {"decision": "deny", "reason": f"no contract on file for {work_item_id}"}

    test_file_path = contract.get("test_file_path")
    recorded_hash = contract.get("test_file_sha256")
    if not test_file_path or not recorded_hash:
        return {
            "decision": "deny",
            "reason": f"malformed contract for {work_item_id}: missing test_file_path or test_file_sha256",
        }

    test_path = project_root / test_file_path
    if not test_path.exists():
        return {
            "decision": "deny",
            "reason": f"test file removed: {test_file_path}",
        }
    if sha256_of(test_path) != recorded_hash:
        return {
            "decision": "deny",
            "reason": "hash mismatch (tampered): test file no longer matches the recorded sha256",
        }

    result = run_test(project_root, test_file_path)
    if result["returncode"] != 0:
        return {
            "decision": "deny",
            "reason": (
                f"contract test still failing (exit {result['returncode']}):\n"
                f"{result['tail']}"
            ),
        }
    return {
        "decision": "allow",
        "reason": f"contract test for {work_item_id} passes and the file is untampered",
    }
