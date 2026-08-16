"""Tests for the findings ledger (scripts/findings.py, design spec 3.3 Task B)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from findings import (  # noqa: E402
    accept_with_reason,
    mark_closed_after_review,
    mark_fixed,
    open_blocking_findings,
    record_finding,
)


@pytest.fixture
def findings_path(tmp_path):
    return tmp_path / "findings.json"


def _statuses(findings_path):
    data = json.loads(findings_path.read_text(encoding="utf-8"))
    return {f["id"]: f["status"] for f in data}


def _blocking_ids(findings_path, **kwargs):
    return [f["id"] for f in open_blocking_findings(findings_path, **kwargs)]


def _record_all(findings_path):
    record_finding(findings_path, "F-01", "P0", "critical", "test_a.py")
    record_finding(findings_path, "F-02", "P1", "major", "test_b.py")
    record_finding(findings_path, "F-03", "P2", "minor", "test_c.py")


def test_record_finding_writes_an_open_entry(findings_path):
    record_finding(findings_path, "F-01", "P0", "critical defect", "test_billing.py")
    assert _statuses(findings_path) == {"F-01": "open"}
    assert _blocking_ids(findings_path) == ["F-01"]


def test_record_finding_rejects_bad_severity(findings_path):
    with pytest.raises(ValueError):
        record_finding(findings_path, "F-01", "P3", "not a real severity", "test_a.py")
    assert not findings_path.exists()


def test_record_finding_rejects_duplicate_id(findings_path):
    record_finding(findings_path, "F-01", "P1", "first", "test_a.py")
    with pytest.raises(ValueError):
        record_finding(findings_path, "F-01", "P1", "duplicate", "test_a.py")


def test_mark_fixed_transitions_open_to_fixed_but_still_blocks(findings_path):
    record_finding(findings_path, "F-01", "P1", "major", "test_a.py")
    mark_fixed(findings_path, "F-01")
    assert _statuses(findings_path) == {"F-01": "fixed"}
    # a fix alone does not clear the gate -- the finding still blocks until reviewed
    assert _blocking_ids(findings_path) == ["F-01"]


def test_mark_fixed_raises_when_not_open(findings_path):
    record_finding(findings_path, "F-01", "P1", "major", "test_a.py")
    mark_fixed(findings_path, "F-01")
    with pytest.raises(ValueError, match="not open"):
        mark_fixed(findings_path, "F-01")


def test_mark_closed_after_review_on_open_finding_raises(findings_path):
    record_finding(findings_path, "F-01", "P1", "major", "test_a.py")
    with pytest.raises(ValueError, match="not fixed"):
        mark_closed_after_review(findings_path, "F-01", "reviewed: no fix exists yet")


def test_mark_closed_after_review_closes_a_fixed_finding(findings_path):
    record_finding(findings_path, "F-01", "P1", "major", "test_a.py")
    mark_fixed(findings_path, "F-01")
    mark_closed_after_review(findings_path, "F-01", "fresh review confirms the fix")
    assert _statuses(findings_path) == {"F-01": "closed"}
    assert _blocking_ids(findings_path) == []
    data = json.loads(findings_path.read_text(encoding="utf-8"))
    assert data[0]["reviewer_note"] == "fresh review confirms the fix"


def test_mark_closed_after_review_skips_no_fixed_state(findings_path):
    # open -> closed directly is impossible; only accept_with_reason may close an open finding
    record_finding(findings_path, "F-01", "P0", "critical", "test_a.py")
    with pytest.raises(ValueError, match="not fixed"):
        mark_closed_after_review(findings_path, "F-01", "never fixed but closing anyway")


def test_accept_with_reason_rejects_empty_reason(findings_path):
    record_finding(findings_path, "F-01", "P0", "critical", "test_a.py")
    with pytest.raises(ValueError, match="non-empty reason"):
        accept_with_reason(findings_path, "F-01", "")
    with pytest.raises(ValueError, match="non-empty reason"):
        accept_with_reason(findings_path, "F-01", "   ")
    assert _statuses(findings_path) == {"F-01": "open"}


def test_accept_with_reason_closes_an_open_finding(findings_path):
    record_finding(findings_path, "F-01", "P0", "critical", "test_a.py")
    accept_with_reason(findings_path, "F-01", "human-accepted: documented workaround shipped")
    assert _statuses(findings_path) == {"F-01": "closed"}
    assert _blocking_ids(findings_path) == []
    data = json.loads(findings_path.read_text(encoding="utf-8"))
    assert data[0]["accepted_reason"] == "human-accepted: documented workaround shipped"


def test_accept_with_reason_closes_a_fixed_finding_too(findings_path):
    record_finding(findings_path, "F-01", "P1", "major", "test_a.py")
    mark_fixed(findings_path, "F-01")
    accept_with_reason(findings_path, "F-01", "accepted at triage despite the fix")
    assert _statuses(findings_path) == {"F-01": "closed"}


def test_open_blocking_findings_returns_p0_and_p1_but_not_p2(findings_path):
    _record_all(findings_path)
    mark_fixed(findings_path, "F-02")  # fixed but unreviewed still blocks
    record_finding(findings_path, "F-04", "P1", "another major", "test_d.py")
    mark_fixed(findings_path, "F-04")
    mark_closed_after_review(findings_path, "F-04", "reviewed and confirmed")
    record_finding(findings_path, "F-05", "P0", "critical", "test_e.py")
    accept_with_reason(findings_path, "F-05", "accepted by human")
    assert _blocking_ids(findings_path) == ["F-01", "F-02"]
    # F-03 is P2 (never blocks by default), F-04 and F-05 are closed
    blocking = open_blocking_findings(findings_path)
    assert [f["id"] for f in blocking] == ["F-01", "F-02"]
    assert all(f["severity"] in ("P0", "P1") for f in blocking)


def test_open_blocking_findings_min_severity_p2_includes_p2(findings_path):
    _record_all(findings_path)
    assert _blocking_ids(findings_path) == ["F-01", "F-02"]
    assert _blocking_ids(findings_path, min_severity="P2") == ["F-01", "F-02", "F-03"]


def test_open_blocking_findings_missing_file_returns_empty(findings_path):
    assert open_blocking_findings(findings_path) == []


def test_mutations_on_missing_ledger_raise_keyerror(findings_path):
    with pytest.raises(KeyError):
        mark_fixed(findings_path, "F-01")
