from pathlib import Path

from scripts import changes, contracts, gate_check
from scripts.loop_state import TaskState, next_action


def test_full_contract_lifecycle(tmp_path):
    changes_dir = tmp_path / "changes"
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()

    change_dir = changes.new_change(changes_dir, "add-widget")
    assert change_dir.exists()

    contract_path = contracts_dir / "functional.md"
    contract_path.write_text(
        "# Functional contract\n\n```contract-check\nassert 1 + 1 == 2\n```\n",
        encoding="utf-8",
    )

    # before approval, the gate denies
    assert gate_check.evaluate(contracts_dir)["decision"] == "deny"

    gate_check.approve_contract(contract_path)
    assert gate_check.evaluate(contracts_dir)["decision"] == "allow"

    result = contracts.run_checks(contract_path)
    assert result == {"passed": True, "failures": []}

    state = TaskState(
        task_id="task-1",
        contract_ref=str(contract_path),
        provider="opencode-go",
        model="qwen3.7-plus",
        rung_exhausted_at_top=False,
        attempts_at_current_rung=0,
        status="done",
    )
    assert next_action(state) == "mark_done"
