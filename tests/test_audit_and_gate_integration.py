from pathlib import Path

from scripts import audit
from scripts.gate_check import approve_contract, evaluate


def test_full_audit_and_gate_flow(tmp_path):
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    contract = contracts_dir / "functional.md"
    contract.write_text("```contract-check\nassert 1 == 1\n```\n", encoding="utf-8")

    assert evaluate(contracts_dir)["decision"] == "deny"
    approve_contract(contract)
    assert evaluate(contracts_dir)["decision"] == "allow"

    rate = audit.sample_rate(consecutive_clean_passes=3, risk_flag_count=0)
    sampled = audit.should_sample(rate, "sub-project-4-dogfood-change")

    # Plugin state lives in the target project, never inside the plugin install location,
    # so the audit log lives under tmp_path here rather than a plugin-root state dir.
    log_path = tmp_path / "sample-log.md"
    audit.log_sample_decision(log_path, "sub-project-4-dogfood-change", rate, sampled)
    text = log_path.read_text(encoding="utf-8")
    assert "sub-project-4-dogfood-change" in text
