import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).parent.parent / "hooks" / "pretooluse_gate.py"
HOOKS_JSON = Path(__file__).parent.parent / "hooks" / "hooks.json"


def _run_hook(payload: dict, contracts_dir: Path, changes_dir: Path | None = None) -> dict:
    env = dict(os.environ)
    env["RATCHET_CONTRACTS_DIR"] = str(contracts_dir)
    # Isolate from the real ../changes directory this hook would otherwise default to --
    # tests must not depend on whatever this repo's own changes/ folder happens to contain.
    env["RATCHET_CHANGES_DIR"] = str(changes_dir) if changes_dir else str(contracts_dir / "_no_changes")
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(result.stdout)


def test_allows_non_write_edit_tools_without_checking_the_gate(tmp_path):
    payload = _run_hook({"tool_name": "Read", "tool_input": {}}, tmp_path)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "allow"
    # Early-return allow must also carry hookEventName -- see regression test below.
    assert payload["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


def test_hook_output_includes_hook_event_name_on_allow_and_deny(tmp_path):
    # Regression for a real live-install bug: Claude Code's PreToolUse schema REQUIRES
    # hookSpecificOutput.hookEventName == "PreToolUse". Without it, Claude Code treats the
    # hook's output as a validation error and fails OPEN -- a write meant to be denied sails
    # through anyway. Neither `claude plugin validate --strict` nor the unit tests caught it
    # because none exercised Claude Code's real hook-execution path; this asserts the raw
    # stdout JSON the hook prints carries the field on every output site.
    #
    # Deny path: no approved contract present.
    empty_contracts = tmp_path / "contracts"
    empty_contracts.mkdir()
    denied = _run_hook({"tool_name": "Write", "tool_input": {}}, empty_contracts)
    assert denied["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"

    # Allow path: an approved contract opens capability.
    contracts_dir = tmp_path / "contracts-approved"
    contracts_dir.mkdir()
    contract = contracts_dir / "functional.md"
    contract.write_text("the contract text", encoding="utf-8")
    digest = hashlib.sha256(contract.read_bytes()).hexdigest()
    (contracts_dir / "functional.md.approved-sha256").write_text(digest, encoding="utf-8")
    allowed = _run_hook({"tool_name": "Write", "tool_input": {}}, contracts_dir)
    assert allowed["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert allowed["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_denies_write_when_no_contract_is_approved(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    payload = _run_hook({"tool_name": "Write", "tool_input": {}}, contracts_dir)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "systemMessage" in payload


def test_allows_write_when_a_contract_is_approved(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    contract = contracts_dir / "functional.md"
    contract.write_text("the contract text", encoding="utf-8")
    digest = hashlib.sha256(contract.read_bytes()).hexdigest()
    (contracts_dir / "functional.md.approved-sha256").write_text(digest, encoding="utf-8")

    payload = _run_hook({"tool_name": "Write", "tool_input": {}}, contracts_dir)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_edit_tool_is_also_gated(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    payload = _run_hook({"tool_name": "Edit", "tool_input": {}}, contracts_dir)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denies_write_when_active_change_has_no_matching_approved_contract(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    contract = contracts_dir / "project-scaffold.md"
    contract.write_text("scaffold contract", encoding="utf-8")
    digest = hashlib.sha256(contract.read_bytes()).hexdigest()
    (contracts_dir / "project-scaffold.md.approved-sha256").write_text(digest, encoding="utf-8")

    changes_dir = tmp_path / "changes"
    (changes_dir / "audio-engine").mkdir(parents=True)

    payload = _run_hook({"tool_name": "Write", "tool_input": {}}, contracts_dir, changes_dir)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "audio-engine" in payload["systemMessage"]


def test_allows_write_when_active_change_has_its_own_approved_contract(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    for name, text in (("project-scaffold.md", "scaffold"), ("audio-engine.md", "audio")):
        contract = contracts_dir / name
        contract.write_text(text, encoding="utf-8")
        digest = hashlib.sha256(contract.read_bytes()).hexdigest()
        (contracts_dir / f"{name}.approved-sha256").write_text(digest, encoding="utf-8")

    changes_dir = tmp_path / "changes"
    (changes_dir / "audio-engine").mkdir(parents=True)

    payload = _run_hook({"tool_name": "Write", "tool_input": {}}, contracts_dir, changes_dir)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_hooks_json_is_valid_for_the_plugin_spec():
    # Plugin hooks files wrap the settings-style PreToolUse list in a "hooks" record (the
    # plugin spec's form of settings.json's hooks section), and the command must resolve
    # through ${CLAUDE_PLUGIN_ROOT} -- the plugin install location -- never a hardcoded path.
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    assert "PreToolUse" in data["hooks"]
    assert data["hooks"]["PreToolUse"][0]["matcher"] == "Write|Edit"
    assert data["hooks"]["PreToolUse"][0]["hooks"][0]["type"] == "command"
    command = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "pretooluse_gate.py" in command
    assert "${CLAUDE_PLUGIN_ROOT}/hooks/pretooluse_gate.py" in command
