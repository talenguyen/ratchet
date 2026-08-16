"""Findings ledger with a severity/status lifecycle (design spec 3.3, Task B).

Storage is a single JSON file -- a list of finding dicts -- at `.ratchet/findings.json`.
This is Ratchet internal bookkeeping for the gate, not the human-facing memory format
(Task C keeps `memory.py`'s own format).

Lifecycle: `open` -> `fixed` -> `closed`. A fix does NOT clear the gate: a finding stays
blocking (status `open` or `fixed`) until a *fresh* review closes it
(`mark_closed_after_review`) or a human accepts it with a recorded reason
(`accept_with_reason`). No one may waive a finding without leaving a reason on file --
that reason is the audit trail `ratchet verify`'s gate rests on.

Severity ordering: P0 worst, P1, P2 least. `open_blocking_findings` returns every
not-yet-closed finding at P0 or the given `min_severity` or worse; the default
`min_severity="P1"` means P2 never blocks unless the caller explicitly raises the bar
to `min_severity="P2"`.
"""
from __future__ import annotations

import json
from pathlib import Path

_SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2}
_VALID_SEVERITIES = frozenset(_SEVERITY_RANK)

# A finding in either of these states is unresolved as far as the gate is concerned:
# `fixed` but not yet re-reviewed is exactly as blocking as `open`.
_BLOCKING_STATUSES = ("open", "fixed")


def _load(findings_path: Path) -> list[dict]:
    if not findings_path.exists():
        return []
    data = json.loads(findings_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{findings_path} must contain a JSON list of findings")
    return data


def _save(findings_path: Path, findings: list[dict]) -> None:
    findings_path.parent.mkdir(parents=True, exist_ok=True)
    findings_path.write_text(json.dumps(findings, indent=2) + "\n", encoding="utf-8")


def _find(findings: list[dict], finding_id: str) -> dict:
    for finding in findings:
        if finding["id"] == finding_id:
            return finding
    raise KeyError(f"no finding with id {finding_id!r}")


def record_finding(
    findings_path: Path, finding_id: str, severity: str, description: str, contract_ref: str
) -> None:
    """Record a new finding with status `open`. Severity must be one of P0/P1/P2."""
    if severity not in _VALID_SEVERITIES:
        raise ValueError(f"severity must be one of P0/P1/P2, got {severity!r}")
    findings = _load(findings_path)
    if any(f["id"] == finding_id for f in findings):
        raise ValueError(f"finding id {finding_id!r} already recorded")
    findings.append({
        "id": finding_id,
        "severity": severity,
        "description": description,
        "contract_ref": contract_ref,
        "status": "open",
    })
    _save(findings_path, findings)


def mark_fixed(findings_path: Path, finding_id: str) -> None:
    """Transition an `open` finding to `fixed`. Raises unless the finding is currently open."""
    findings = _load(findings_path)
    finding = _find(findings, finding_id)
    if finding["status"] != "open":
        raise ValueError(
            f"finding {finding_id!r} is {finding['status']}, not open -- only open findings "
            "can be marked fixed"
        )
    finding["status"] = "fixed"
    _save(findings_path, findings)


def mark_closed_after_review(findings_path: Path, finding_id: str, reviewer_note: str) -> None:
    """Close a `fixed` finding after a fresh review looked at the result.

    Raises unless the finding is currently `fixed`: closing requires the fix to have been
    made AND reviewed -- `open` findings never skip straight to closed via review (the
    only route from `open` to `closed` without a fix is `accept_with_reason`).
    """
    findings = _load(findings_path)
    finding = _find(findings, finding_id)
    if finding["status"] != "fixed":
        raise ValueError(
            f"finding {finding_id!r} is {finding['status']}, not fixed -- a fresh review "
            "may only close a finding whose fix has been made"
        )
    finding["status"] = "closed"
    finding["reviewer_note"] = reviewer_note
    _save(findings_path, findings)


def accept_with_reason(findings_path: Path, finding_id: str, reason: str) -> None:
    """Close an `open` or `fixed` finding because a human accepted it, recording the reason.

    Raises ValueError if the reason is empty: an acceptance with no reason on file is
    exactly the silent waiver the ledger exists to prevent.
    """
    if not reason.strip():
        raise ValueError("accepting a finding requires a non-empty reason")
    findings = _load(findings_path)
    finding = _find(findings, finding_id)
    if finding["status"] not in _BLOCKING_STATUSES:
        raise ValueError(
            f"finding {finding_id!r} is already {finding['status']} -- only open or fixed "
            "findings can be accepted"
        )
    finding["status"] = "closed"
    finding["accepted_reason"] = reason
    _save(findings_path, findings)


def open_blocking_findings(findings_path: Path, min_severity: str = "P1") -> list[dict]:
    """Every finding that would block `ratchet verify`: status open or fixed (not yet
    closed), at severity P0 or the given `min_severity` or worse. P2 never blocks with the
    default `min_severity="P1"`.
    """
    if min_severity not in _VALID_SEVERITIES:
        raise ValueError(f"min_severity must be one of P0/P1/P2, got {min_severity!r}")
    findings = _load(findings_path)
    max_rank = _SEVERITY_RANK[min_severity]
    return [
        finding
        for finding in findings
        if finding["status"] in _BLOCKING_STATUSES
        and _SEVERITY_RANK[finding["severity"]] <= max_rank
    ]
