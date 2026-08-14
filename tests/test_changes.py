import pytest

from scripts.changes import new_change


def test_new_change_creates_expected_files(tmp_path):
    change_dir = new_change(tmp_path, "add-thing")
    assert change_dir == tmp_path / "add-thing"
    assert (change_dir / "proposal.md").exists()
    assert (change_dir / "contract-delta.md").exists()
    assert (change_dir / "tasks.md").exists()
    assert not (change_dir / "design.md").exists()


def test_contract_delta_has_added_modified_removed_headers(tmp_path):
    change_dir = new_change(tmp_path, "add-thing")
    text = (change_dir / "contract-delta.md").read_text(encoding="utf-8")
    assert "## ADDED Requirements" in text
    assert "## MODIFIED Requirements" in text
    assert "## REMOVED Requirements" in text


def test_new_change_raises_if_slug_already_exists(tmp_path):
    new_change(tmp_path, "add-thing")
    with pytest.raises(FileExistsError):
        new_change(tmp_path, "add-thing")
