import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "memory.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_record_then_recall_round_trips_through_the_cli(tmp_path):
    memory_path = tmp_path / "instincts.json"
    record = _run_cli("record", str(memory_path), "android-ui", "slug-matched contracts", "d175d74", "0.8")
    assert record.returncode == 0

    recalled = _run_cli("recall", str(memory_path), "0.5", "6")
    assert recalled.returncode == 0
    payload = json.loads(recalled.stdout)
    assert any(e["pattern"] == "slug-matched contracts" for e in payload["entries"])


def test_contradict_via_cli_removes_it_from_recall(tmp_path):
    memory_path = tmp_path / "instincts.json"
    _run_cli("record", str(memory_path), "x", "pattern", "ref1", "0.9")
    contradict = _run_cli("contradict", str(memory_path), "x", "pattern")
    assert json.loads(contradict.stdout)["marked"] == 1

    recalled = json.loads(_run_cli("recall", str(memory_path), "0.0", "6").stdout)
    assert recalled["entries"] == []


def test_cli_usage_error_on_missing_args():
    result = _run_cli()
    assert result.returncode == 2


def test_record_cli_rejects_bad_confidence(tmp_path):
    memory_path = tmp_path / "instincts.json"
    result = _run_cli("record", str(memory_path), "x", "y", "z", "1.5")
    assert result.returncode == 2
