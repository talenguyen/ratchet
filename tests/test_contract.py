"""Tests for Mechanism 1: scripts/contract.py (red-before-green + sha256 sidecar).

Each test builds a tiny project in a tmp_path: a `demo.py` module at the project
root and a contract test file under ratchet/contracts/<id>/. The contract test
imports `demo`, which resolves because `python3 -m pytest` puts the working
directory (project_root) on sys.path. "Implementing" means editing demo.py only;
any edit to the contract test file itself is a tamper that the hash sidecar must
catch.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.contract import (  # noqa: E402
    approve_contract,
    can_implement,
    characterize_contract,
    propose_contract,
    run_test,
    sha256_of,
    verify_complete,
)

CONTRACT_TEST = """\
import demo

def test_contract():
    assert demo.add(2, 3) == 5
"""

DEMO_IMPLEMENTED = """\
def add(a, b):
    return a + b
"""


def make_project(tmp_path: Path, demo_code: str = "") -> Path:
    """A project root with a demo module (unimplemented stub by default)."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "demo.py").write_text(demo_code, encoding="utf-8")
    return project


def make_contract_test(project: Path, work_item_id: str, body: str = CONTRACT_TEST) -> str:
    """Write the contract test file under ratchet/contracts/<id>/, return its
    project-relative path (the value that goes into contract.json)."""
    test_path = project / "ratchet" / "contracts" / work_item_id / "test_contract.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(body, encoding="utf-8")
    return str(test_path.relative_to(project))


def contract_json(project: Path, work_item_id: str) -> dict:
    return json.loads(
        (project / "ratchet" / "contracts" / work_item_id / "contract.json").read_text(
            encoding="utf-8"
        )
    )


def proposed(project: Path, work_item_id: str = "W-001") -> dict:
    return propose_contract(project, work_item_id, make_contract_test(project, work_item_id))


def approved(project: Path, work_item_id: str = "W-001") -> dict:
    proposed(project, work_item_id)
    return approve_contract(project, work_item_id, "graham")


# --- primitives -------------------------------------------------------------


def test_sha256_of_is_hex_of_file_bytes(tmp_path):
    project = make_project(tmp_path)
    demo = project / "demo.py"
    assert sha256_of(demo) == hashlib.sha256(demo.read_bytes()).hexdigest()


def test_run_test_distinguishes_pass_fail_no_tests(tmp_path):
    project = make_project(tmp_path, demo_code=DEMO_IMPLEMENTED)
    (project / "test_pass.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )
    (project / "test_fail.py").write_text(
        "def test_bad():\n    assert 1 + 1 == 3\n", encoding="utf-8"
    )
    (project / "test_none.py").write_text("x = 1\n", encoding="utf-8")

    r = run_test(project, "test_pass.py")
    assert r["returncode"] == 0 and r["tail"]
    r = run_test(project, "test_fail.py")
    assert r["returncode"] == 1 and r["tail"]
    r = run_test(project, "test_none.py")
    assert r["returncode"] == 5


# --- propose -----------------------------------------------------------------


def test_propose_denies_passing_test_and_writes_nothing(tmp_path):
    project = make_project(tmp_path, demo_code=DEMO_IMPLEMENTED)
    rel = make_contract_test(project, "W-001")
    result = propose_contract(project, "W-001", rel)
    assert result["decision"] == "deny"
    assert "make it fail first" in result["reason"]
    assert not (project / "ratchet" / "contracts" / "W-001" / "contract.json").exists()


def test_propose_allows_failing_test_and_writes_contract(tmp_path):
    project = make_project(tmp_path)  # demo has no add -> runtime failure -> exit 1
    rel = make_contract_test(project, "W-001")
    result = propose_contract(project, "W-001", rel)
    assert result["decision"] == "allow"
    contract = contract_json(project, "W-001")
    assert contract["work_item_id"] == "W-001"
    assert contract["test_file_path"] == rel
    assert contract["test_file_sha256"] == sha256_of(project / rel)
    assert contract["fail_mode_evidence"]  # non-empty captured failure tail
    assert contract["approved_by"] is None
    assert contract["approved_at"] is None
    assert contract["kind"] == "new_work"


def test_propose_denies_no_tests_collected(tmp_path):
    project = make_project(tmp_path)
    rel = make_contract_test(project, "W-001", body="x = 1\n")
    result = propose_contract(project, "W-001", rel)
    assert result["decision"] == "deny"
    assert "no tests" in result["reason"]


# --- approve -----------------------------------------------------------------


def test_approve_denies_when_no_contract_proposed(tmp_path):
    project = make_project(tmp_path)
    result = approve_contract(project, "W-001", "graham")
    assert result["decision"] == "deny"
    assert "no proposed contract for W-001" in result["reason"]


def test_approve_denies_when_test_file_changed_since_propose(tmp_path):
    project = make_project(tmp_path)
    proposed(project)
    test_path = project / "ratchet" / "contracts" / "W-001" / "test_contract.py"
    test_path.write_text(CONTRACT_TEST + "# drift\n", encoding="utf-8")  # still failing, but new bytes
    result = approve_contract(project, "W-001", "graham")
    assert result["decision"] == "deny"
    assert "changed since propose" in result["reason"]


def test_approve_denies_when_test_now_passes_before_approval(tmp_path):
    project = make_project(tmp_path)
    proposed(project)
    # Someone implemented early: demo fixed, contract test untouched (hash intact).
    (project / "demo.py").write_text(DEMO_IMPLEMENTED, encoding="utf-8")
    result = approve_contract(project, "W-001", "graham")
    assert result["decision"] == "deny"
    assert "before approval" in result["reason"]


def test_approve_allows_normal_case_and_stamps_approval(tmp_path):
    project = make_project(tmp_path)
    proposed(project)
    result = approve_contract(project, "W-001", "graham")
    assert result["decision"] == "allow"
    assert "still failing" in result["reason"]  # new_work expects still-red
    contract = contract_json(project, "W-001")
    assert contract["approved_by"] == "graham"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", contract["approved_at"])


# --- characterize_contract -----------------------------------------------------


def test_characterize_denies_failing_capture(tmp_path):
    project = make_project(tmp_path)  # demo has no add -> the capture would FAIL
    rel = make_contract_test(project, "W-002")
    result = characterize_contract(project, "W-002", rel)
    assert result["decision"] == "deny"
    assert "wrong capture" in result["reason"]
    assert not (project / "ratchet" / "contracts" / "W-002" / "contract.json").exists()


def test_characterize_denies_no_tests_collected(tmp_path):
    project = make_project(tmp_path)
    rel = make_contract_test(project, "W-002", body="x = 1\n")
    result = characterize_contract(project, "W-002", rel)
    assert result["decision"] == "deny"
    assert "no tests" in result["reason"].lower()


def test_characterize_allows_passing_capture_and_writes_kind(tmp_path):
    project = make_project(tmp_path, demo_code=DEMO_IMPLEMENTED)
    rel = make_contract_test(project, "W-002")
    result = characterize_contract(project, "W-002", rel)
    assert result["decision"] == "allow"
    contract = contract_json(project, "W-002")
    assert contract["kind"] == "characterization"
    assert contract["work_item_id"] == "W-002"
    assert contract["test_file_path"] == rel
    assert contract["test_file_sha256"] == sha256_of(project / rel)
    assert contract["fail_mode_evidence"]  # the passing run's output
    assert contract["approved_by"] is None
    assert contract["approved_at"] is None


# --- approve, kind-aware --------------------------------------------------------


def test_approve_allows_characterization_and_stamps(tmp_path):
    project = make_project(tmp_path, demo_code=DEMO_IMPLEMENTED)
    rel = make_contract_test(project, "W-002")
    assert characterize_contract(project, "W-002", rel)["decision"] == "allow"

    result = approve_contract(project, "W-002", "graham")
    assert result["decision"] == "allow"
    assert "still passing" in result["reason"]  # characterization expects still-green
    contract = contract_json(project, "W-002")
    assert contract["kind"] == "characterization"
    assert contract["approved_by"] == "graham"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", contract["approved_at"])


def test_approve_denies_characterization_when_behavior_drifted(tmp_path):
    project = make_project(tmp_path, demo_code=DEMO_IMPLEMENTED)
    rel = make_contract_test(project, "W-002")
    assert characterize_contract(project, "W-002", rel)["decision"] == "allow"

    # The underlying behavior drifts: add(2, 3) is now 6, so the capture no longer passes.
    (project / "demo.py").write_text(
        "def add(a, b):\n    return a + b + 1\n", encoding="utf-8"
    )
    result = approve_contract(project, "W-002", "graham")
    assert result["decision"] == "deny"
    assert "no longer passes" in result["reason"]
    assert contract_json(project, "W-002")["approved_by"] is None  # not stamped


def test_approve_denies_characterization_when_test_tampered(tmp_path):
    project = make_project(tmp_path, demo_code=DEMO_IMPLEMENTED)
    rel = make_contract_test(project, "W-002")
    assert characterize_contract(project, "W-002", rel)["decision"] == "allow"

    # Tamper: test file bytes changed after propose (still passes — assertion intact).
    test_path = project / "ratchet" / "contracts" / "W-002" / "test_contract.py"
    test_path.write_text(CONTRACT_TEST + "# tampered\n", encoding="utf-8")
    result = approve_contract(project, "W-002", "graham")
    assert result["decision"] == "deny"
    assert "changed since propose" in result["reason"]  # sha256 path, not the kind branch


# --- can_implement ------------------------------------------------------------


def test_can_implement_false_before_approval(tmp_path):
    project = make_project(tmp_path)
    proposed(project)
    result = can_implement(project, "W-001")
    assert result["allowed"] is False
    assert "not approved" in result["reason"]


def test_can_implement_true_after_approval(tmp_path):
    project = make_project(tmp_path)
    approved(project)
    result = can_implement(project, "W-001")
    assert result["allowed"] is True


def test_can_implement_false_after_test_file_tamper(tmp_path):
    project = make_project(tmp_path)
    approved(project)
    test_path = project / "ratchet" / "contracts" / "W-001" / "test_contract.py"
    test_path.write_text(CONTRACT_TEST + "# tampered\n", encoding="utf-8")
    result = can_implement(project, "W-001")
    assert result["allowed"] is False
    assert "changed since approval" in result["reason"]


# --- verify_complete ----------------------------------------------------------


def test_verify_complete_denies_while_still_failing(tmp_path):
    project = make_project(tmp_path)
    approved(project)  # nothing implemented
    result = verify_complete(project, "W-001")
    assert result["decision"] == "deny"
    assert "still failing" in result["reason"]


def test_verify_complete_denies_tampered_even_if_test_passes(tmp_path):
    project = make_project(tmp_path)
    approved(project)
    # Tamper: replace the contract test with a trivial passing test, demo untouched.
    test_path = project / "ratchet" / "contracts" / "W-001" / "test_contract.py"
    test_path.write_text("def test_trivially_passes():\n    assert True\n", encoding="utf-8")
    result = verify_complete(project, "W-001")
    assert result["decision"] == "deny"
    assert "hash mismatch" in result["reason"]


def test_verify_complete_denies_removed_test_file(tmp_path):
    project = make_project(tmp_path)
    approved(project)
    (project / "ratchet" / "contracts" / "W-001" / "test_contract.py").unlink()
    result = verify_complete(project, "W-001")
    assert result["decision"] == "deny"
    assert "removed" in result["reason"]


def test_verify_complete_allows_green_untampered(tmp_path):
    project = make_project(tmp_path)
    approved(project)
    (project / "demo.py").write_text(DEMO_IMPLEMENTED, encoding="utf-8")  # implement, test untouched
    result = verify_complete(project, "W-001")
    assert result["decision"] == "allow"
