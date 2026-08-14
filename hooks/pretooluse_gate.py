#!/usr/bin/env python3
"""Claude Code PreToolUse hook: enforce Ratchet's capability gate (design spec section 4)
before Write/Edit tools run. This wires gate_check.evaluate() into Claude Code's actual
hook JSON contract.

This is the bundled, read-only copy inside the plugin install location. All contract/change
STATE lives in the TARGET project being worked on, under `ratchet-state/` at the project
root -- never inside the plugin. The project root is taken from CLAUDE_PROJECT_DIR (set by
Claude Code for hooks) with a cwd fallback.

RATCHET_CONTRACTS_DIR overrides the contracts directory (for isolated testing); Claude Code
itself never needs to set it -- the default is <project>/ratchet-state/contracts.
RATCHET_CHANGES_DIR likewise overrides ratchet-state/changes, and enables per-change gate
scoping (gate_check.active_change_slugs) so the gate can no longer be satisfied once,
anywhere, and stay open forever for later, uncontracted changes (see lesson 028).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gate_check import evaluate


def main() -> int:
    payload = json.loads(sys.stdin.read())
    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        # Claude Code's PreToolUse schema requires hookSpecificOutput.hookEventName; without it
        # the output is a validation error and Claude Code fails OPEN (allows the tool anyway).
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }))
        return 0

    # State lives in the target project, not in this plugin's install location. Claude Code
    # sets CLAUDE_PROJECT_DIR for hooks; fall back to cwd for direct/test invocation.
    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())

    contracts_override = os.environ.get("RATCHET_CONTRACTS_DIR")
    contracts_dir = (
        Path(contracts_override)
        if contracts_override
        else project_root / "ratchet-state" / "contracts"
    )
    changes_override = os.environ.get("RATCHET_CHANGES_DIR")
    changes_dir = (
        Path(changes_override)
        if changes_override
        else project_root / "ratchet-state" / "changes"
    )
    result = evaluate(contracts_dir, changes_dir)

    decision = "allow" if result["decision"] == "allow" else "deny"
    output = {
        "hookSpecificOutput": {
            # Required by Claude Code's PreToolUse schema; missing it turns the decision into a
            # validation error and Claude Code fails OPEN instead of honoring the deny.
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
        }
    }
    if decision == "deny":
        output["systemMessage"] = f"Ratchet capability gate denied this write: {result['reason']}"
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
