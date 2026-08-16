"""Tests for the brownfield baseline: scripts/baseline.py.

Each test builds a small project in tmp_path with real pytest test files; test
IDs are parsed from real pytest output, so these are integration-style tests
against the actual subprocess command.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.baseline import check_no_new_failures, record_baseline  # noqa: E402

TEST_CMD = "python3 -m pytest -q"


def make_project(tmp_path: Path) -> Path:
    """A project with 2 passing tests and 2 pre-existing failing tests (old debt)."""
    project = tmp_path / "project"
    (project / "tests").mkdir(parents=True)
    (project / "tests" / "test_ok.py").write_text(
        "def test_good_one():\n    assert 1 + 1 == 2\n"
        "def test_good_two():\n    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )
    (project / "tests" / "test_debt.py").write_text(
        "def test_old_debt_one():\n    assert False\n"
        "def test_old_debt_two():\n    assert 1 == 2\n",
        encoding="utf-8",
    )
    return project


def test_record_baseline_records_both_pre_existing_failures(tmp_path):
    project = make_project(tmp_path)
    baseline = tmp_path / "baseline.json"
    result = record_baseline(project, TEST_CMD, baseline)
    assert result == {"failures_recorded": 2}

    data = json.loads(baseline.read_text(encoding="utf-8"))
    assert data["test_command"] == TEST_CMD
    assert data["recorded_at"].endswith("Z")  # ISO 8601 UTC
    assert data["pre_existing_failures"] == [
        "tests/test_debt.py::test_old_debt_one",
        "tests/test_debt.py::test_old_debt_two",
    ]


def test_check_no_new_failures_same_state_allows(tmp_path):
    project = make_project(tmp_path)
    baseline = tmp_path / "baseline.json"
    record_baseline(project, TEST_CMD, baseline)

    result = check_no_new_failures(project, TEST_CMD, baseline)
    assert result["decision"] == "allow"
    assert result["new_failures"] == []


def test_check_no_new_failures_denies_naming_exactly_the_new_test(tmp_path):
    project = make_project(tmp_path)
    baseline = tmp_path / "baseline.json"
    record_baseline(project, TEST_CMD, baseline)

    # Simulate a real regression: break a previously-passing test.
    (project / "tests" / "test_ok.py").write_text(
        "def test_good_one():\n    assert 1 + 1 == 2\n"
        "def test_good_two():\n    assert 2 + 2 == 5\n",  # now failing
        encoding="utf-8",
    )
    result = check_no_new_failures(project, TEST_CMD, baseline)
    assert result["decision"] == "deny"
    assert result["new_failures"] == ["tests/test_ok.py::test_good_two"]
    assert "test_good_two" in result["reason"]


def test_check_no_new_failures_missing_baseline_denies_specifically(tmp_path):
    project = make_project(tmp_path)
    result = check_no_new_failures(project, TEST_CMD, tmp_path / "nope.json")
    assert result["decision"] == "deny"
    assert result["new_failures"] == []
    assert "no baseline recorded" in result["reason"]


def test_check_no_new_failures_fixing_pre_existing_debt_still_allows(tmp_path):
    project = make_project(tmp_path)
    baseline = tmp_path / "baseline.json"
    record_baseline(project, TEST_CMD, baseline)

    # Fix the old debt: both debt tests now pass. Fixing pre-existing failures
    # is never a regression.
    (project / "tests" / "test_debt.py").write_text(
        "def test_old_debt_one():\n    assert True\n"
        "def test_old_debt_two():\n    assert 1 == 1\n",
        encoding="utf-8",
    )
    result = check_no_new_failures(project, TEST_CMD, baseline)
    assert result["decision"] == "allow"
    assert result["new_failures"] == []
