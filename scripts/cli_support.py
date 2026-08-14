"""Shared shell-out plumbing for this project's `allow`/`deny`-shaped CLI entry points.

Extracted once `gate_check.py`'s and `security.py`'s `main()` functions started repeating the
same "print the decision as JSON, exit 0 on allow else 1" footer -- caught by this project's own
quality gate on itself (duplicate_lines), not invented ahead of need.
"""
from __future__ import annotations

import json


def emit_decision(result: dict) -> int:
    """Print `result` as JSON and return the process exit code its `decision` field implies."""
    print(json.dumps(result))
    return 0 if result["decision"] == "allow" else 1
