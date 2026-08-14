import hashlib
from pathlib import Path

from scripts import gate_check


def _write_approved_contract(dir_path: Path, name: str, content: str) -> Path:
    contract = dir_path / name
    contract.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(contract.read_bytes()).hexdigest()
    sidecar = contract.with_suffix(contract.suffix + ".approved-sha256")
    sidecar.write_text(digest, encoding="utf-8")
    return contract


def test_contract_is_approved_true_when_hash_matches(tmp_path):
    contract = _write_approved_contract(tmp_path, "functional.md", "the contract text")
    assert gate_check.contract_is_approved(contract) is True


def test_contract_is_approved_false_when_edited_after_approval(tmp_path):
    contract = _write_approved_contract(tmp_path, "functional.md", "the contract text")
    contract.write_text("the contract text, edited", encoding="utf-8")
    assert gate_check.contract_is_approved(contract) is False


def test_contract_is_approved_false_when_sidecar_missing(tmp_path):
    contract = tmp_path / "functional.md"
    contract.write_text("the contract text", encoding="utf-8")
    assert gate_check.contract_is_approved(contract) is False


def test_evaluate_denies_when_no_contracts_dir(tmp_path):
    result = gate_check.evaluate(tmp_path / "does-not-exist")
    assert result["decision"] == "deny"


def test_evaluate_denies_when_no_approved_contract(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    (contracts_dir / "functional.md").write_text("unapproved draft", encoding="utf-8")
    result = gate_check.evaluate(contracts_dir)
    assert result["decision"] == "deny"


def test_evaluate_allows_when_a_contract_is_approved(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    _write_approved_contract(contracts_dir, "functional.md", "the contract text")
    result = gate_check.evaluate(contracts_dir)
    assert result["decision"] == "allow"


def test_approve_contract_creates_matching_sidecar(tmp_path):
    contract = tmp_path / "functional.md"
    contract.write_text("the contract text", encoding="utf-8")
    gate_check.approve_contract(contract)
    assert gate_check.contract_is_approved(contract) is True


def test_approve_contract_overwrites_stale_sidecar(tmp_path):
    contract = tmp_path / "functional.md"
    contract.write_text("version one", encoding="utf-8")
    gate_check.approve_contract(contract)
    contract.write_text("version two", encoding="utf-8")
    assert gate_check.contract_is_approved(contract) is False
    gate_check.approve_contract(contract)
    assert gate_check.contract_is_approved(contract) is True


def test_active_change_slugs_lists_in_progress_changes(tmp_path):
    changes_dir = tmp_path / "changes"
    (changes_dir / "audio-engine").mkdir(parents=True)
    (changes_dir / "dark-theme").mkdir(parents=True)
    (changes_dir / "archive" / "2026-08-01-old-change").mkdir(parents=True)
    assert gate_check.active_change_slugs(changes_dir) == ["audio-engine", "dark-theme"]


def test_active_change_slugs_empty_when_no_changes_dir(tmp_path):
    assert gate_check.active_change_slugs(tmp_path / "does-not-exist") == []


def test_evaluate_still_allows_globally_when_changes_dir_not_passed(tmp_path):
    # Backward compatibility: callers that don't opt into per-change scoping keep the old,
    # weaker "any approved contract" behavior.
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    _write_approved_contract(contracts_dir, "project-scaffold.md", "the contract text")
    result = gate_check.evaluate(contracts_dir)
    assert result["decision"] == "allow"


def test_evaluate_denies_when_active_change_has_no_matching_approved_contract(tmp_path):
    # This is lesson 028's exact failure mode: one contract approved anywhere used to be
    # enough to keep the gate open forever, even for a second, third, fourth change that
    # never got its own contract drafted at all.
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    _write_approved_contract(contracts_dir, "project-scaffold.md", "the contract text")

    changes_dir = tmp_path / "changes"
    (changes_dir / "audio-engine").mkdir(parents=True)  # in progress, no contract of its own

    result = gate_check.evaluate(contracts_dir, changes_dir)
    assert result["decision"] == "deny"
    assert "audio-engine" in result["reason"]


def test_evaluate_allows_when_every_active_change_has_its_own_approved_contract(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    _write_approved_contract(contracts_dir, "project-scaffold.md", "scaffold contract")
    _write_approved_contract(contracts_dir, "audio-engine.md", "audio engine contract")

    changes_dir = tmp_path / "changes"
    (changes_dir / "audio-engine").mkdir(parents=True)

    result = gate_check.evaluate(contracts_dir, changes_dir)
    assert result["decision"] == "allow"


def test_evaluate_ignores_archived_changes_for_scoping(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    _write_approved_contract(contracts_dir, "project-scaffold.md", "scaffold contract")

    changes_dir = tmp_path / "changes"
    (changes_dir / "archive" / "2026-08-01-audio-engine").mkdir(parents=True)

    result = gate_check.evaluate(contracts_dir, changes_dir)
    assert result["decision"] == "allow"
