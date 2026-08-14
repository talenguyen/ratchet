import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "gate_check.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )


def test_cli_exits_zero_and_allows_when_contract_approved(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    contract = contracts_dir / "functional.md"
    contract.write_text("the contract text", encoding="utf-8")
    digest = hashlib.sha256(contract.read_bytes()).hexdigest()
    (contracts_dir / "functional.md.approved-sha256").write_text(digest, encoding="utf-8")

    result = _run_cli(str(contracts_dir))
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "allow"


def test_cli_exits_nonzero_and_denies_when_no_contract(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    result = _run_cli(str(contracts_dir))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["decision"] == "deny"


def test_cli_usage_error_on_wrong_arg_count():
    result = _run_cli()
    assert result.returncode == 2


def test_cli_denies_when_changes_dir_arg_has_uncontracted_active_change(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    contract = contracts_dir / "project-scaffold.md"
    contract.write_text("scaffold contract", encoding="utf-8")
    digest = hashlib.sha256(contract.read_bytes()).hexdigest()
    (contracts_dir / "project-scaffold.md.approved-sha256").write_text(digest, encoding="utf-8")

    changes_dir = tmp_path / "changes"
    (changes_dir / "audio-engine").mkdir(parents=True)

    result = _run_cli(str(contracts_dir), str(changes_dir))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["decision"] == "deny"
    assert "audio-engine" in payload["reason"]
