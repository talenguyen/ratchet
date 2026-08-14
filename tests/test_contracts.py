from pathlib import Path

from scripts import contracts


def test_extract_checks_finds_single_block(tmp_path):
    contract = tmp_path / "functional.md"
    contract.write_text(
        "# Contract\n\nSome prose.\n\n```contract-check\nassert 1 + 1 == 2\n```\n",
        encoding="utf-8",
    )
    blocks = contracts.extract_checks(contract)
    assert blocks == ["assert 1 + 1 == 2"]


def test_extract_checks_finds_multiple_blocks(tmp_path):
    contract = tmp_path / "functional.md"
    contract.write_text(
        "```contract-check\nassert 1 == 1\n```\n\nmore prose\n\n"
        "```contract-check\nassert 2 == 2\n```\n",
        encoding="utf-8",
    )
    blocks = contracts.extract_checks(contract)
    assert blocks == ["assert 1 == 1", "assert 2 == 2"]


def test_run_checks_all_pass(tmp_path):
    contract = tmp_path / "functional.md"
    contract.write_text("```contract-check\nassert 1 + 1 == 2\n```\n", encoding="utf-8")
    result = contracts.run_checks(contract)
    assert result == {"passed": True, "failures": []}


def test_run_checks_reports_failure_without_stopping_others(tmp_path):
    contract = tmp_path / "functional.md"
    contract.write_text(
        "```contract-check\nassert 1 == 2\n```\n\n"
        "```contract-check\nassert 3 == 3\n```\n",
        encoding="utf-8",
    )
    result = contracts.run_checks(contract)
    assert result["passed"] is False
    assert len(result["failures"]) == 1
    assert "assert 1 == 2" in result["failures"][0]
