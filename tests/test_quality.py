from pathlib import Path

from scripts import quality


def test_cyclomatic_complexity_counts_branches(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text(
        "def simple():\n"
        "    return 1\n\n"
        "def branchy(x):\n"
        "    if x:\n"
        "        return 1\n"
        "    else:\n"
        "        return 2\n",
        encoding="utf-8",
    )
    scores = quality.cyclomatic_complexity(f)
    assert scores["simple"] == 1
    assert scores["branchy"] == 2


def test_duplicate_line_count_finds_shared_long_lines(tmp_path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    shared = "    return some_function_call(argument_one, argument_two)"
    a.write_text(f"def f():\n{shared}\n", encoding="utf-8")
    b.write_text(f"def g():\n{shared}\n", encoding="utf-8")
    assert quality.duplicate_line_count([a, b]) == 1


def test_duplicate_line_count_ignores_short_lines(tmp_path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("x = 1\n", encoding="utf-8")
    b.write_text("x = 1\n", encoding="utf-8")
    assert quality.duplicate_line_count([a, b]) == 0


def test_duplicate_line_count_excludes_plain_import_statements(tmp_path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    shared_import = "from datetime import datetime, timezone"
    a.write_text(f"{shared_import}\n", encoding="utf-8")
    b.write_text(f"{shared_import}\n", encoding="utf-8")
    assert quality.duplicate_line_count([a, b]) == 0


def test_compute_scores_aggregates_across_paths(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text(
        "def simple():\n    return 1\n\ndef branchy(x):\n    if x:\n        return 1\n    else:\n        return 2\n",
        encoding="utf-8",
    )
    scores = quality.compute_scores([f])
    assert scores["avg_complexity"] == 1.5
    assert scores["duplicate_lines"] == 0


def test_check_ratchet_passes_with_no_baseline():
    result = quality.check_ratchet({"avg_complexity": 5.0}, None)
    assert result == {"passed": True, "regressions": []}


def test_check_ratchet_fails_when_a_metric_regresses():
    result = quality.check_ratchet(
        {"avg_complexity": 6.0, "duplicate_lines": 0},
        {"avg_complexity": 5.0, "duplicate_lines": 0},
    )
    assert result["passed"] is False
    assert result["regressions"] == ["avg_complexity"]


def test_check_ratchet_passes_when_metrics_hold_or_improve():
    result = quality.check_ratchet(
        {"avg_complexity": 4.0, "duplicate_lines": 0},
        {"avg_complexity": 5.0, "duplicate_lines": 0},
    )
    assert result == {"passed": True, "regressions": []}


def test_save_and_load_baseline_roundtrip(tmp_path):
    path = tmp_path / "FITNESS.json"
    quality.save_baseline(path, {"avg_complexity": 3.5})
    assert quality.load_baseline(path) == {"avg_complexity": 3.5}


def test_load_baseline_missing_file_returns_none(tmp_path):
    assert quality.load_baseline(tmp_path / "missing.json") is None
