import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ratchet_core import (  # noqa: E402
    approve,
    approved_sidecar_path,
    is_approved,
    load_config,
    run_pytest,
    sha256_of,
    verify,
)


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".ratchet" / "approved").mkdir(parents=True)
    (tmp_path / ".ratchet" / "config.json").write_text(
        json.dumps({"test_command": "python3 -m pytest"}), encoding="utf-8"
    )
    (tmp_path / "tests" / "contracts").mkdir(parents=True)
    return tmp_path


def _write_contract(project, slug, body):
    path = project / "tests" / "contracts" / f"test_{slug}.py"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_config_reads_test_command(project):
    assert load_config(project) == {"test_command": "python3 -m pytest"}


def test_load_config_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path)


def test_sha256_of_matches_hashlib(project):
    import hashlib

    contract = _write_contract(project, "demo", "def test_demo():\n    assert False\n")
    assert sha256_of(contract) == hashlib.sha256(contract.read_bytes()).hexdigest()


def test_is_approved_false_until_sidecar_matches(project):
    contract = _write_contract(project, "demo", "def test_demo():\n    assert False\n")
    assert is_approved(project, contract) is False
    approved_sidecar_path(project, "demo").write_text(sha256_of(contract), encoding="utf-8")
    assert is_approved(project, contract) is True


def test_run_pytest_uses_the_configured_test_command_not_a_hardcoded_interpreter(project):
    # Found live while dogfooding on a project needing `uv run pytest` (its own managed venv):
    # a hardcoded sys.executable can't see a package that only exists in that environment.
    # Prove the config value is genuinely read by pointing test_command at a command that
    # cannot exist -- if this were still hardcoded, it would silently run real pytest instead.
    (project / ".ratchet" / "config.json").write_text(
        json.dumps({"test_command": "definitely-not-a-real-test-runner-xyz"}), encoding="utf-8"
    )
    contract = _write_contract(project, "demo", "def test_demo():\n    assert True\n")
    with pytest.raises(FileNotFoundError):
        run_pytest(project, target=str(contract))


def test_run_pytest_reports_no_tests_collected(project):
    contract = _write_contract(project, "empty", "# no test functions here\n")
    result = run_pytest(project, target=str(contract))
    assert result["returncode"] == 5


def test_run_pytest_reports_pass(project):
    contract = _write_contract(project, "demo", "def test_demo():\n    assert True\n")
    result = run_pytest(project, target=str(contract))
    assert result["returncode"] == 0


def test_run_pytest_reports_fail(project):
    contract = _write_contract(project, "demo", "def test_demo():\n    assert False\n")
    result = run_pytest(project, target=str(contract))
    assert result["returncode"] == 1


def test_approve_denies_a_contract_with_no_tests(project):
    contract = _write_contract(project, "empty", "# nothing\n")
    result = approve(project, contract)
    assert result["decision"] == "deny"
    assert "no tests" in result["reason"]
    assert not approved_sidecar_path(project, "empty").exists()


def test_approve_denies_a_contract_that_already_passes(project):
    contract = _write_contract(project, "tauto", "def test_tauto():\n    assert 1 == 1\n")
    result = approve(project, contract)
    assert result["decision"] == "deny"
    assert "already" in result["reason"].lower()
    assert not approved_sidecar_path(project, "tauto").exists()


def test_approve_allows_a_failing_contract_and_writes_sidecar(project):
    (project / 'app').mkdir()
    (project / 'app' / 'billing.py').write_text('def total(x):\n    return x * 2\n', encoding='utf-8')
    contract = _write_contract(
        project, 'billing', 'from app.billing import total\n\ndef test_billing():\n    assert total(2) == 999\n'
    )
    result = approve(project, contract)
    assert result['decision'] == 'allow'
    assert approved_sidecar_path(project, 'billing').exists()
    assert approved_sidecar_path(project, 'billing').read_text(encoding='utf-8') == sha256_of(contract)


def test_verify_denies_when_contract_edited_after_approval(project):
    contract = _write_contract(project, "demo", "def test_demo():\n    assert False\n")
    approve(project, contract)
    contract.write_text("def test_demo():\n    assert True\n", encoding="utf-8")  # edited post-approval
    result = verify(project, contract)
    assert result["decision"] == "deny"
    assert "changed since approval" in result["reason"]


def test_verify_denies_when_full_suite_fails(project):
    contract = _write_contract(project, "demo", "def test_demo():\n    assert False\n")
    approve(project, contract)
    (project / "app").mkdir()
    (project / "app" / "billing.py").write_text("def total(x):\n    return x * 2\n", encoding="utf-8")
    contract.write_text(
        "from app.billing import total\n\ndef test_demo():\n    assert total(2) == 4\n", encoding="utf-8"
    )
    approved_sidecar_path(project, "demo").write_text(sha256_of(contract), encoding="utf-8")
    _write_contract(project, "other", "def test_other():\n    assert 1 == 2\n")  # unrelated failing test
    result = verify(project, contract)
    assert result["decision"] == "deny"
    assert "test suite failing" in result["reason"]


def test_verify_allows_when_contract_and_full_suite_pass(project):
    (project / 'app').mkdir()
    (project / 'app' / 'billing.py').write_text('def total(x):\n    return x * 3\n', encoding='utf-8')
    contract = _write_contract(
        project, 'demo', 'from app.billing import total\n\ndef test_demo():\n    assert total(2) == 4\n'
    )
    approve_result = approve(project, contract)
    assert approve_result['decision'] == 'allow'
    (project / 'app' / 'billing.py').write_text('def total(x):\n    return x * 2\n', encoding='utf-8')
    result = verify(project, contract)
    assert result['decision'] == 'allow'
