import json
import subprocess
import sys
from pathlib import Path

from scripts.progress import mark_step_done
from scripts.task_state_store import resumable_tasks

SCRIPT = Path(__file__).parent.parent / "scripts" / "task_state_store.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def _write_checklist(project_root: Path, slug: str, lines: str) -> Path:
    path = project_root / "tests" / "contracts" / f"{slug}.progress.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(lines, encoding="utf-8")
    return path


def test_resumable_tasks_finds_checklists_with_unchecked_steps(tmp_path):
    _write_checklist(tmp_path, "demo", "- [ ] step one\n- [ ] step two\n")
    _write_checklist(tmp_path, "other", "- [x] only step, done\n")

    tasks = resumable_tasks(tmp_path)
    assert len(tasks) == 1
    assert tasks[0] == {
        "slug": "demo",
        "progress_path": "tests/contracts/demo.progress.md",
        "next_step": "step one",
    }


def test_resumable_tasks_reads_next_step_from_the_file_directly(tmp_path):
    path = _write_checklist(tmp_path, "demo", "- [ ] first\n- [ ] second\n- [ ] third\n")
    mark_step_done(path, "first")

    tasks = resumable_tasks(tmp_path)
    assert tasks[0]["slug"] == "demo"
    assert tasks[0]["next_step"] == "second"


def test_resumable_tasks_excludes_fully_checked_checklists(tmp_path):
    _write_checklist(tmp_path, "done", "- [x] one\n- [x] two\n")
    assert resumable_tasks(tmp_path) == []


def test_resumable_tasks_empty_when_no_contracts_dir(tmp_path):
    assert resumable_tasks(tmp_path) == []
    assert resumable_tasks(tmp_path / "does-not-exist") == []


def test_resumable_tasks_sorts_by_slug(tmp_path):
    for slug, lines in [("zeta", "- [ ] z\n"), ("alpha", "- [ ] a\n"), ("mid", "- [ ] m\n")]:
        _write_checklist(tmp_path, slug, lines)
    assert [t["slug"] for t in resumable_tasks(tmp_path)] == ["alpha", "mid", "zeta"]


def test_resumable_tasks_ignores_non_progress_md_files(tmp_path):
    _write_checklist(tmp_path, "demo", "- [ ] step one\n")
    (tmp_path / "tests" / "contracts" / "test_demo.py").write_text("def test_x(): pass\n", encoding="utf-8")
    (tmp_path / "tests" / "contracts" / "README.md").write_text("- [ ] not a checklist\n", encoding="utf-8")
    assert len(resumable_tasks(tmp_path)) == 1


def test_cli_resumable_prints_slug_and_next_step(tmp_path):
    _write_checklist(tmp_path, "demo", "- [x] first\n- [ ] second\n")
    result = _run_cli("resumable", str(tmp_path))
    assert result.returncode == 0
    tasks = json.loads(result.stdout)["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["slug"] == "demo"
    assert tasks[0]["next_step"] == "second"
    assert tasks[0]["progress_path"] == "tests/contracts/demo.progress.md"


def test_cli_resumable_prints_no_tasks_when_all_checked(tmp_path):
    _write_checklist(tmp_path, "demo", "- [x] done\n")
    result = _run_cli("resumable", str(tmp_path))
    assert result.returncode == 0
    assert json.loads(result.stdout)["tasks"] == []


def test_cli_next_step_prints_first_unchecked_step(tmp_path):
    path = _write_checklist(tmp_path, "demo", "- [ ] open\n- [ ] later\n")
    result = _run_cli("next-step", str(path))
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["progress_path"] == str(path)
    assert payload["next_step"] == "open"


def test_cli_next_step_prints_null_when_nothing_left(tmp_path):
    path = _write_checklist(tmp_path, "demo", "- [x] done\n")
    result = _run_cli("next-step", str(path))
    assert result.returncode == 0
    assert json.loads(result.stdout)["next_step"] is None


def test_cli_next_step_prints_null_for_missing_file(tmp_path):
    result = _run_cli("next-step", str(tmp_path / "nope.progress.md"))
    assert result.returncode == 0
    assert json.loads(result.stdout)["next_step"] is None


def test_cli_usage_error_on_missing_args():
    result = _run_cli()
    assert result.returncode == 2
    assert "usage" in json.loads(result.stdout)["error"]
