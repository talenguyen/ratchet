from pathlib import Path

import pytest

from scripts.progress import first_unchecked_step, mark_step_done


def _write_checklist(tmp_path: Path, lines: str) -> Path:
    path = tmp_path / "demo.progress.md"
    path.write_text(lines, encoding="utf-8")
    return path


def test_first_unchecked_step_missing_file_returns_none(tmp_path):
    assert first_unchecked_step(tmp_path / "never-existed.progress.md") is None


def test_first_unchecked_step_empty_checklist_returns_none(tmp_path):
    path = _write_checklist(tmp_path, "")
    assert first_unchecked_step(path) is None


def test_first_unchecked_step_ignores_non_checklist_lines(tmp_path):
    path = _write_checklist(
        tmp_path,
        "# demo\n\nSome prose, not a step.\n\n- [ ] first step\n- [ ] second step\n",
    )
    assert first_unchecked_step(path) == "first step"


def test_first_unchecked_step_returns_first_unchecked_in_file_order(tmp_path):
    path = _write_checklist(tmp_path, "- [x] done step\n- [ ] first open\n- [ ] second open\n")
    assert first_unchecked_step(path) == "first open"


def test_first_unchecked_step_all_checked_returns_none(tmp_path):
    path = _write_checklist(tmp_path, "- [x] one\n- [x] two\n- [x] three\n")
    assert first_unchecked_step(path) is None


def test_mark_step_done_then_reread_shows_checked(tmp_path):
    path = _write_checklist(tmp_path, "- [ ] one\n- [ ] two\n")
    mark_step_done(path, "one")
    assert first_unchecked_step(path) == "two"
    assert "- [x] one" in path.read_text(encoding="utf-8")


def test_mark_step_done_checks_only_first_matching_line(tmp_path):
    path = _write_checklist(tmp_path, "- [ ] one\n- [ ] one\n- [ ] two\n")
    mark_step_done(path, "one")
    text = path.read_text(encoding="utf-8")
    assert text.count("- [x] one") == 1
    assert text.count("- [ ] one") == 1


def test_mark_step_done_preserves_step_text_exactly(tmp_path):
    path = _write_checklist(tmp_path, "- [ ] scaffold tests/contracts/demo.progress.md\n")
    mark_step_done(path, "scaffold tests/contracts/demo.progress.md")
    assert "- [x] scaffold tests/contracts/demo.progress.md" in path.read_text(encoding="utf-8")


def test_mark_step_done_nonexistent_step_raises(tmp_path):
    path = _write_checklist(tmp_path, "- [ ] one\n- [ ] two\n")
    with pytest.raises(ValueError):
        mark_step_done(path, "not on the list")


def test_mark_step_done_already_checked_step_raises(tmp_path):
    path = _write_checklist(tmp_path, "- [x] one\n- [ ] two\n")
    with pytest.raises(ValueError):
        mark_step_done(path, "one")


def test_mark_step_done_missing_file_raises(tmp_path):
    with pytest.raises(ValueError):
        mark_step_done(tmp_path / "never-existed.progress.md", "anything")
