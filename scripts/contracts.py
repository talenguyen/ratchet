"""Extract and run the falsifiable checks embedded in a contract file (design spec section 3).

A contract file is an ordinary markdown document containing one or more
fenced ```contract-check code blocks; each block is a self-contained Python
snippet whose assertions define what must hold. This operationalizes
"falsifiable, ideally executable" without inventing a bespoke contract DSL.
"""
from __future__ import annotations

import builtins
import re
from pathlib import Path

_BLOCK_RE = re.compile(r"```contract-check\n(.*?)```", re.DOTALL)


def extract_checks(contract_path: Path) -> list[str]:
    """Return the source of every ```contract-check fenced block, in document order."""
    text = contract_path.read_text(encoding="utf-8")
    return [match.strip() for match in _BLOCK_RE.findall(text)]


def run_checks(contract_path: Path) -> dict:
    """Execute every check block independently and report pass/fail.

    Each block runs via exec() in its own fresh namespace -- one block's
    AssertionError or exception is recorded as a failure and does not stop
    the remaining blocks from running, so a single bad check doesn't hide
    the status of the others.
    """
    failures: list[str] = []
    for block in extract_checks(contract_path):
        try:
            exec(block, {"__builtins__": builtins})
        except Exception as exc:
            failures.append(f"{block}\n--- raised: {exc!r}")
    return {"passed": not failures, "failures": failures}
