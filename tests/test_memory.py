from pathlib import Path

from scripts import memory


def test_record_instinct_creates_file_with_one_entry(tmp_path):
    path = tmp_path / "instincts"
    memory.record_instinct(path, "android-ui", "screens ship with slug-matched contracts", "d175d74")
    entries = memory.load_instincts(path)
    assert len(entries) == 1
    assert entries[0].task_class == "android-ui"
    assert entries[0].evidence_ref == "d175d74"
    # one human-readable Markdown file per instinct, frontmatter + pattern body
    files = list(path.glob("*.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert text.startswith("---\ntask_class: android-ui\n")
    assert "screens ship with slug-matched contracts" in text


def test_record_instinct_rejects_confidence_out_of_range(tmp_path):
    path = tmp_path / "instincts"
    try:
        memory.record_instinct(path, "x", "y", "z", confidence=1.5)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_record_instinct_defaults_to_low_confidence(tmp_path):
    path = tmp_path / "instincts"
    memory.record_instinct(path, "x", "y", "z")
    entries = memory.load_instincts(path)
    assert entries[0].confidence <= 0.5


def test_load_instincts_empty_when_directory_missing(tmp_path):
    assert memory.load_instincts(tmp_path / "does-not-exist") == []


def test_recall_excludes_low_confidence_by_default(tmp_path):
    path = tmp_path / "instincts"
    memory.record_instinct(path, "x", "weak pattern", "ref1", confidence=0.2)
    memory.record_instinct(path, "x", "strong pattern", "ref2", confidence=0.8)
    recalled = memory.recall(path)
    patterns = [e.pattern for e in recalled]
    assert "strong pattern" in patterns
    assert "weak pattern" not in patterns


def test_recall_ranks_by_confidence_descending(tmp_path):
    path = tmp_path / "instincts"
    memory.record_instinct(path, "x", "medium", "ref1", confidence=0.6)
    memory.record_instinct(path, "x", "highest", "ref2", confidence=0.9)
    recalled = memory.recall(path, min_confidence=0.0)
    assert [e.pattern for e in recalled][:2] == ["highest", "medium"]


def test_recall_respects_limit(tmp_path):
    path = tmp_path / "instincts"
    for i in range(10):
        memory.record_instinct(path, "x", f"pattern-{i}", f"ref{i}", confidence=0.9)
    recalled = memory.recall(path, min_confidence=0.0, limit=3)
    assert len(recalled) == 3


def test_contradict_instinct_marks_matching_entries(tmp_path):
    path = tmp_path / "instincts"
    memory.record_instinct(path, "x", "pattern", "ref1", confidence=0.9)
    marked = memory.contradict_instinct(path, "x", "pattern")
    assert marked == 1
    entries = memory.load_instincts(path)
    assert entries[0].contradicted is True


def test_recall_excludes_contradicted_entries_even_at_high_confidence(tmp_path):
    path = tmp_path / "instincts"
    memory.record_instinct(path, "x", "pattern", "ref1", confidence=0.9)
    memory.contradict_instinct(path, "x", "pattern")
    recalled = memory.recall(path, min_confidence=0.0)
    assert recalled == []


def test_contradict_instinct_returns_zero_when_nothing_matches(tmp_path):
    path = tmp_path / "instincts"
    memory.record_instinct(path, "x", "pattern", "ref1", confidence=0.9)
    marked = memory.contradict_instinct(path, "y", "different pattern")
    assert marked == 0


def test_record_instinct_requires_an_evidence_reference(tmp_path):
    path = tmp_path / "instincts"
    try:
        memory.record_instinct(path, "x", "y", "")
        assert False, "expected ValueError for empty evidence_ref"
    except ValueError:
        pass
