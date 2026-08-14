import json

from scripts import rung_stats


def test_load_missing_file_returns_empty_list(tmp_path):
    entries = rung_stats.load(tmp_path / "missing.json")
    assert entries == []


def test_record_outcome_creates_new_entry(tmp_path):
    path = tmp_path / "rung_stats.json"
    rung_stats.record_outcome(
        path,
        task_class="rename-mechanical",
        provider="opencode-go",
        model="deepseek-v4-flash",
        passed=True,
        cost_usd=0.01,
        latency_s=5.0,
    )
    entries = rung_stats.load(path)
    assert len(entries) == 1
    assert entries[0].task_class == "rename-mechanical"
    assert entries[0].attempts == 1
    assert entries[0].passes == 1
    assert entries[0].pass_rate == 1.0
    assert entries[0].avg_cost_usd == 0.01


def test_record_outcome_accumulates_into_existing_entry(tmp_path):
    path = tmp_path / "rung_stats.json"
    rung_stats.record_outcome(
        path, "rename-mechanical", "opencode-go", "deepseek-v4-flash", True, 0.01, 5.0
    )
    rung_stats.record_outcome(
        path, "rename-mechanical", "opencode-go", "deepseek-v4-flash", False, 0.02, 6.0
    )
    entries = rung_stats.load(path)
    assert len(entries) == 1
    assert entries[0].attempts == 2
    assert entries[0].passes == 1
    assert entries[0].pass_rate == 0.5
    assert abs(entries[0].avg_cost_usd - 0.015) < 1e-9


def test_save_is_readable_json(tmp_path):
    path = tmp_path / "rung_stats.json"
    rung_stats.record_outcome(
        path, "rename-mechanical", "opencode-go", "deepseek-v4-flash", True, 0.01, 5.0
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "entries" in raw
    assert raw["entries"][0]["task_class"] == "rename-mechanical"

def test_lookup_starting_rung_returns_none_when_no_data(tmp_path):
    rung_path = tmp_path / "rung_stats.json"
    providers_path = tmp_path / "PROVIDERS.md"
    providers_path.write_text(
        "| Provider | Model | Allowed |\n|---|---|---|\n"
        "| opencode-go | deepseek-v4-flash | yes |\n",
        encoding="utf-8",
    )
    result = rung_stats.lookup_starting_rung(rung_path, providers_path, "rename-mechanical")
    assert result is None


def test_lookup_starting_rung_picks_cheapest_allowed_passing_entry(tmp_path):
    rung_path = tmp_path / "rung_stats.json"
    providers_path = tmp_path / "PROVIDERS.md"
    providers_path.write_text(
        "| Provider | Model | Allowed |\n|---|---|---|\n"
        "| opencode-go | deepseek-v4-flash | yes |\n"
        "| opencode-go | qwen3.7-plus | yes |\n",
        encoding="utf-8",
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "deepseek-v4-flash", True, 0.01, 5.0
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "qwen3.7-plus", True, 0.05, 5.0
    )
    result = rung_stats.lookup_starting_rung(rung_path, providers_path, "rename-mechanical")
    assert result is not None
    assert result.model == "deepseek-v4-flash"


def test_lookup_starting_rung_excludes_disallowed_provider(tmp_path):
    rung_path = tmp_path / "rung_stats.json"
    providers_path = tmp_path / "PROVIDERS.md"
    providers_path.write_text(
        "| Provider | Model | Allowed |\n|---|---|---|\n"
        "| opencode-go | deepseek-v4-flash | no |\n"
        "| opencode-go | qwen3.7-plus | yes |\n",
        encoding="utf-8",
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "deepseek-v4-flash", True, 0.01, 5.0
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "qwen3.7-plus", True, 0.05, 5.0
    )
    result = rung_stats.lookup_starting_rung(rung_path, providers_path, "rename-mechanical")
    assert result is not None
    assert result.model == "qwen3.7-plus"


def test_lookup_starting_rung_excludes_entries_below_min_pass_rate(tmp_path):
    rung_path = tmp_path / "rung_stats.json"
    providers_path = tmp_path / "PROVIDERS.md"
    providers_path.write_text(
        "| Provider | Model | Allowed |\n|---|---|---|\n"
        "| opencode-go | deepseek-v4-flash | yes |\n"
        "| opencode-go | qwen3.7-plus | yes |\n",
        encoding="utf-8",
    )
    # deepseek passes only 1/3 -- below the default 0.8 threshold
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "deepseek-v4-flash", True, 0.01, 5.0
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "deepseek-v4-flash", False, 0.01, 5.0
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "deepseek-v4-flash", False, 0.01, 5.0
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "qwen3.7-plus", True, 0.05, 5.0
    )
    result = rung_stats.lookup_starting_rung(rung_path, providers_path, "rename-mechanical")
    assert result is not None
    assert result.model == "qwen3.7-plus"
