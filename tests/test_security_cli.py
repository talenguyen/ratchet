import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "security.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_scan_contract_cli_denies_on_high_severity_finding(tmp_path):
    contract = tmp_path / "risky.md"
    contract.write_text("```contract-check\nsubprocess.run(['rm', '-rf', '/'])\n```\n", encoding="utf-8")
    result = _run_cli("scan-contract", str(contract))
    assert result.returncode == 1
    assert json.loads(result.stdout)["decision"] == "deny"


def test_scan_contract_cli_allows_clean_contract(tmp_path):
    contract = tmp_path / "clean.md"
    contract.write_text("```contract-check\nassert 1 == 1\n```\n", encoding="utf-8")
    result = _run_cli("scan-contract", str(contract))
    assert result.returncode == 0
    assert json.loads(result.stdout)["decision"] == "allow"


def test_scan_secrets_cli_denies_when_finding_present(tmp_path):
    dirty = tmp_path / "dirty.py"
    dirty.write_text("token: 'abcdefgh12345678'\n", encoding="utf-8")
    result = _run_cli("scan-secrets", str(dirty))
    assert result.returncode == 1
    assert json.loads(result.stdout)["decision"] == "deny"


def test_cli_usage_error_on_missing_args():
    result = _run_cli()
    assert result.returncode == 2


def test_cli_usage_error_on_unknown_command(tmp_path):
    result = _run_cli("bogus-command", str(tmp_path))
    assert result.returncode == 2
