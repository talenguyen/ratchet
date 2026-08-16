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
        rung_path, "rename-mechanical", "opencode-go", "deepseek-v4-flash", True, 0.01, 5.0
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "deepseek-v4-flash", True, 0.01, 5.0
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "qwen3.7-plus", True, 0.05, 5.0
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "qwen3.7-plus", True, 0.05, 5.0
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
        rung_path, "rename-mechanical", "opencode-go", "deepseek-v4-flash", True, 0.01, 5.0
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "deepseek-v4-flash", True, 0.01, 5.0
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "qwen3.7-plus", True, 0.05, 5.0
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "qwen3.7-plus", True, 0.05, 5.0
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
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "qwen3.7-plus", True, 0.05, 5.0
    )
    rung_stats.record_outcome(
        rung_path, "rename-mechanical", "opencode-go", "qwen3.7-plus", True, 0.05, 5.0
    )
    result = rung_stats.lookup_starting_rung(rung_path, providers_path, "rename-mechanical")
    assert result is not None
    assert result.model == "qwen3.7-plus"


def test_lookup_starting_rung_requires_a_minimum_sample_size(tmp_path):
    stats_path = tmp_path / "RUNG_STATS.json"
    providers_path = tmp_path / "PROVIDERS.md"
    providers_path.write_text(
        "| Provider | Model | Allowed |\n"
        "|---|---|---|\n"
        "| opencode-go | deepseek-v4-flash | yes |\n",
        encoding="utf-8",
    )

    rung_stats.record_outcome(stats_path, "build-feature", "opencode-go", "deepseek-v4-flash", True, 0.0, 0.0)
    # One attempt, one pass -- pass_rate is 1.0, but the sample size (1) is below the default
    # minimum (3). The old bug: this alone used to qualify as "proven."
    assert rung_stats.lookup_starting_rung(stats_path, providers_path, "build-feature") is None

    rung_stats.record_outcome(stats_path, "build-feature", "opencode-go", "deepseek-v4-flash", True, 0.0, 0.0)
    rung_stats.record_outcome(stats_path, "build-feature", "opencode-go", "deepseek-v4-flash", True, 0.0, 0.0)
    # Now attempts=3, still qualifies (pass_rate 1.0 >= 0.8, attempts 3 >= min_attempts 3)
    entry = rung_stats.lookup_starting_rung(stats_path, providers_path, "build-feature")
    assert entry is not None
    assert entry.attempts == 3


def _seed_baseline(path, task_class="build-feature", provider="opencode-go", model="qwen3.7-plus"):
    """One recorded outcome -> attempts=1, avg_cost_usd=0.01, avg_latency_s=5.0."""
    rung_stats.record_outcome(
        path, task_class, provider, model, passed=True, cost_usd=0.01, latency_s=5.0
    )


def test_over_budget_no_baseline_is_not_flagged(tmp_path):
    path = tmp_path / "rung_stats.json"
    result = rung_stats.over_budget(path, "never-seen", "p", "m", 9.99, 999.0)
    assert result == {"flagged": False, "reason": "no baseline yet"}


def test_over_budget_both_under_is_not_flagged(tmp_path):
    path = tmp_path / "rung_stats.json"
    _seed_baseline(path)
    result = rung_stats.over_budget(path, "build-feature", "opencode-go", "qwen3.7-plus", 0.02, 10.0)
    assert result == {"flagged": False, "reason": None}


def test_over_budget_cost_over_is_flagged_naming_cost(tmp_path):
    path = tmp_path / "rung_stats.json"
    _seed_baseline(path)  # avg cost 0.01 -> 3x limit 0.03
    result = rung_stats.over_budget(path, "build-feature", "opencode-go", "qwen3.7-plus", 0.05, 10.0)
    assert result["flagged"] is True
    assert "cost" in result["reason"]
    assert "latency" not in result["reason"]


def test_over_budget_latency_over_is_flagged_naming_latency(tmp_path):
    path = tmp_path / "rung_stats.json"
    _seed_baseline(path)  # avg latency 5.0 -> 3x limit 15.0
    result = rung_stats.over_budget(path, "build-feature", "opencode-go", "qwen3.7-plus", 0.02, 20.0)
    assert result["flagged"] is True
    assert "latency" in result["reason"]
    assert "cost" not in result["reason"]


def test_over_budget_both_over_is_flagged_naming_both(tmp_path):
    path = tmp_path / "rung_stats.json"
    _seed_baseline(path)
    result = rung_stats.over_budget(path, "build-feature", "opencode-go", "qwen3.7-plus", 0.05, 20.0)
    assert result["flagged"] is True
    assert "cost" in result["reason"]
    assert "latency" in result["reason"]
