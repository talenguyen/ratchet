"""Characterize existing behavior into a contract (design spec
2026-08-16-ratchet-foundational-gaps.md section 2 / Task 1).

The inverse of ratchet_core.approve: a characterization test's entire purpose is
asserting current, already-true behavior as a regression safety net, so it must PASS
against the current code to be a valid capture -- a characterization test that fails
is testing the wrong thing (a typo in the recorded value, not real behavior).

Reuses ratchet_core.run_pytest/sha256_of/approved_sidecar_path -- pytest invocation
and sidecar writing are not reimplemented a second way.
"""
from __future__ import annotations

from pathlib import Path

try:
    from scripts.ratchet_core import approved_sidecar_path, run_pytest, sha256_of
except ImportError:
    from ratchet_core import approved_sidecar_path, run_pytest, sha256_of

_NO_TESTS_COLLECTED = 5
_CHARACTERIZATION_DIR = Path("tests") / "contracts" / "characterization"


def characterize(project_root: Path, contract_path: Path) -> dict:
    """Inverse of ratchet_core.approve: reject if the new characterization test FAILS against
    current code (wrong capture, not real behavior); on pass, write the same tamper-evident sidecar
    approve() uses. Returns {"decision": "allow"|"deny", "reason": str}."""
    try:
        contract_path.relative_to(project_root / _CHARACTERIZATION_DIR)
    except ValueError:
        return {
            "decision": "deny",
            "reason": (
                f"{contract_path} is not under {project_root / _CHARACTERIZATION_DIR} -- "
                "characterization contracts live in tests/contracts/characterization/ so they stay "
                "distinguishable from approve()'s new-work contracts by convention, not just by "
                "which command was run"
            ),
        }

    result = run_pytest(project_root, target=str(contract_path))
    if result["returncode"] == _NO_TESTS_COLLECTED:
        return {
            "decision": "deny",
            "reason": f"{contract_path} defines no tests -- nothing captured to characterize",
        }
    if result["returncode"] != 0:
        if result["returncode"] != 1:
            return {
                "decision": "deny",
                "reason": f"pytest error (exit {result['returncode']}): {result['tail']}",
            }
        return {
            "decision": "deny",
            "reason": (
                f"{contract_path} FAILS against the current code -- a characterization test that "
                "fails is a wrong capture (a typo in the recorded value), not real behavior; "
                "re-run the target and record what it actually returns:\n"
                f"{result['tail']}"
            ),
        }

    slug = contract_path.stem.removeprefix("test_")
    sidecar = approved_sidecar_path(project_root, slug)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(sha256_of(contract_path), encoding="utf-8")
    return {
        "decision": "allow",
        "reason": f"characterized {contract_path} (currently passing, as required)",
    }
