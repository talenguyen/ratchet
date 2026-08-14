"""Structural capability gate (design spec section 4): deny writes until a contract is approved.

This module defines the gate's own decision logic and (Task 6) a small CLI
any harness's hook mechanism can shell out to. Wiring this into a specific
harness's native hook system (e.g. Claude Code's PreToolUse hook JSON
schema) is out of scope here — see the Claude Code packaging sub-project.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

try:
    from scripts.cli_support import emit_decision
except ImportError:
    from cli_support import emit_decision


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contract_is_approved(contract_path: Path) -> bool:
    """True if an `.approved-sha256` sidecar exists and matches the contract's current hash.

    The sidecar is written by the approval step (design spec section 10,
    human touchpoint 1) once a human approves a contract — that step is
    built in the contract-acquisition sub-project, not here. This function
    only checks the resulting state.
    """
    sidecar = contract_path.with_suffix(contract_path.suffix + ".approved-sha256")
    if not contract_path.exists() or not sidecar.exists():
        return False
    recorded = sidecar.read_text(encoding="utf-8").strip()
    return recorded == sha256_of(contract_path)


def approve_contract(contract_path: Path) -> None:
    """Write the `.approved-sha256` sidecar `contract_is_approved()` checks against.

    This is human touchpoint 1 (design spec section 10) made concrete:
    approving a contract is recording its current hash as the approved one.
    """
    sidecar = contract_path.with_suffix(contract_path.suffix + ".approved-sha256")
    sidecar.write_text(sha256_of(contract_path), encoding="utf-8")


def active_change_slugs(changes_dir: Path) -> list[str]:
    """Slugs of changes currently in progress under `changes_dir` -- i.e. everything except
    the `archive/` folder itself. A change stops being "active" the moment `changes.archive_change`
    moves it under `archive/`, which is exactly the signal this gate needs to know a change no
    longer requires its own approved contract to keep capability open.
    """
    if not changes_dir.is_dir():
        return []
    return sorted(d.name for d in changes_dir.iterdir() if d.is_dir() and d.name != "archive")


def evaluate(contracts_dir: Path, changes_dir: Path | None = None) -> dict:
    """Decide whether write/edit capability should be open, given a contracts directory.

    Base gate: capability is open only if at least one `*.md` contract file under
    `contracts_dir` is currently approved.

    Per-change scoping (lesson 028): a single approved contract anywhere used to be enough to
    keep the gate open forever, so a project mid-way through several declared changes could ship
    two, three, four changes deep with no contract ever drafted for the later ones -- the first
    approval was already "enough". When `changes_dir` is passed, every change still in progress
    (per `active_change_slugs`) must have its *own* approved contract, matched by filename stem
    (change slug `audio-engine` <-> contract `contracts/**/audio-engine.md`) -- the convention
    this project's own sessions already followed by hand before this function enforced it.
    `changes_dir` is optional so existing callers keep the old, weaker global behavior unless they
    explicitly opt into per-change scoping.
    """
    if not contracts_dir.is_dir():
        return {"decision": "deny", "reason": f"no contracts directory at {contracts_dir}"}
    contract_files = sorted(contracts_dir.rglob("*.md"))
    approved = [c for c in contract_files if contract_is_approved(c)]
    if not approved:
        return {
            "decision": "deny",
            "reason": "no approved contract found under " + str(contracts_dir),
        }

    if changes_dir is not None:
        pending = active_change_slugs(changes_dir)
        approved_slugs = {c.stem for c in approved}
        uncovered = [slug for slug in pending if slug not in approved_slugs]
        if uncovered:
            return {
                "decision": "deny",
                "reason": (
                    f"active change(s) missing their own approved contract: {uncovered} "
                    f"(approved contracts present: {sorted(approved_slugs)})"
                ),
            }

    return {
        "decision": "allow",
        "reason": f"approved contract present: {approved[0]}",
    }


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print(json.dumps({
            "decision": "deny",
            "reason": "usage: gate_check.py <contracts_dir> [changes_dir]",
        }))
        return 2
    changes_dir = Path(argv[2]) if len(argv) == 3 else None
    result = evaluate(Path(argv[1]), changes_dir)
    return emit_decision(result)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
