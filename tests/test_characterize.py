import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from characterize import characterize  # noqa: E402
from ratchet_core import approved_sidecar_path, sha256_of  # noqa: E402


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".ratchet" / "approved").mkdir(parents=True)
    (tmp_path / ".ratchet" / "config.json").write_text(
        json.dumps({"test_command": "python3 -m pytest"}), encoding="utf-8"
    )
    (tmp_path / "tests" / "contracts" / "characterization").mkdir(parents=True)
    return tmp_path


def _write_characterization(project, slug, body):
    path = project / "tests" / "contracts" / "characterization" / f"test_{slug}.py"
    path.write_text(body, encoding="utf-8")
    return path


# The function under characterization everywhere in this file: rounds half away from
# zero (2.5 -> 3, -2.5 -> -3) -- the kind of current behavior a naive assumption
# (e.g. round-half-to-even, or truncation) would get wrong, which is exactly what a
# characterization test exists to pin down.
_HALF_ROUND_IMPL = (
    "def half_round(x):\n"
    "    return int(x + 0.5) if x >= 0 else int(x - 0.5)\n"
)


def test_characterize_allows_a_passing_capture_and_writes_sidecar(project):
    (project / "app").mkdir()
    (project / "app" / "rounder.py").write_text(_HALF_ROUND_IMPL, encoding="utf-8")
    contract = _write_characterization(
        project,
        "rounder",
        "from app.rounder import half_round\n"
        "\n"
        "def test_rounds_half_away_from_zero():\n"
        "    assert half_round(2.5) == 3\n"
        "    assert half_round(-2.5) == -3\n",
    )
    result = characterize(project, contract)
    assert result["decision"] == "allow"
    # same tamper-evident sidecar approve() uses, same content contract
    assert approved_sidecar_path(project, "rounder").exists()
    assert approved_sidecar_path(project, "rounder").read_text(encoding="utf-8") == sha256_of(
        contract
    )


def test_characterize_denies_a_wrong_capture_and_writes_no_sidecar(project):
    (project / "app").mkdir()
    (project / "app" / "rounder.py").write_text(_HALF_ROUND_IMPL, encoding="utf-8")
    contract = _write_characterization(
        project,
        "rounder",
        # deliberately wrong captured value: -2.5 actually returns -3, not -2
        "from app.rounder import half_round\n"
        "\n"
        "def test_rounds_half_away_from_zero():\n"
        "    assert half_round(2.5) == 3\n"
        "    assert half_round(-2.5) == -2\n",
    )
    result = characterize(project, contract)
    assert result["decision"] == "deny"
    assert "fails" in result["reason"].lower()
    assert not approved_sidecar_path(project, "rounder").exists()


def test_characterize_denies_a_contract_outside_characterization_dir(project):
    contract = project / "tests" / "contracts" / "test_new_work.py"
    contract.write_text("def test_new_work():\n    assert True\n", encoding="utf-8")
    result = characterize(project, contract)
    assert result["decision"] == "deny"
    assert "characterization" in result["reason"].lower()
    assert not approved_sidecar_path(project, "new_work").exists()


def test_characterize_denies_a_file_with_no_tests(project):
    contract = _write_characterization(project, "empty", "# no test functions here\n")
    result = characterize(project, contract)
    assert result["decision"] == "deny"
    assert "no tests" in result["reason"].lower()
    assert not approved_sidecar_path(project, "empty").exists()
