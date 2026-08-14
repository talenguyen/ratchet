from pathlib import Path

from scripts import gate_check, providers, rung_stats

# The plugin bundles no project state -- contracts/changes/audit/runs/RUNG_STATS.json live in
# the TARGET project being worked on (ratchet-state/), so these tests build their own state
# files under tmp_path instead of reading the dogfood repo's live ones.


def _write_providers(path: Path) -> None:
    path.write_text(
        "# Providers\n\n"
        "| Provider | Model | Allowed |\n"
        "|---|---|---|\n"
        "| opencode-go | deepseek-v4-flash | yes |\n"
        "| opencode-go | qwen3.7-plus | yes |\n"
        "| legacy-go | old-model | no |\n",
        encoding="utf-8",
    )


def _write_rung_stats(path: Path) -> None:
    path.write_text(
        '{"entries": [{"attempts": 1, "last_updated": "2026-08-12T00:00:00+00:00",'
        ' "model": "qwen3.7-plus", "passes": 1, "provider": "opencode-go",'
        ' "task_class": "small-single-function-addition", "total_cost_usd": 0.02632,'
        ' "total_latency_s": 101.581}]}\n',
        encoding="utf-8",
    )


def test_real_providers_file_parses(tmp_path):
    providers_file = tmp_path / "PROVIDERS.md"
    _write_providers(providers_file)
    entries = providers.parse_providers(providers_file)
    assert len(entries) >= 1
    assert all(isinstance(e["allowed"], bool) for e in entries)


def test_real_rung_stats_file_is_structurally_valid(tmp_path):
    stats_file = tmp_path / "RUNG_STATS.json"
    _write_rung_stats(stats_file)
    entries = rung_stats.load(stats_file)
    assert isinstance(entries, list)
    for entry in entries:
        assert entry.attempts >= 1
        assert 0.0 <= entry.pass_rate <= 1.0


def test_lookup_against_real_files_returns_none_before_any_runs(tmp_path):
    stats_file = tmp_path / "RUNG_STATS.json"
    providers_file = tmp_path / "PROVIDERS.md"
    _write_rung_stats(stats_file)
    _write_providers(providers_file)
    result = rung_stats.lookup_starting_rung(
        stats_file, providers_file, "any-task-class"
    )
    assert result is None


def test_gate_denies_before_any_contract_exists(tmp_path):
    empty_contracts_dir = tmp_path / "contracts"
    empty_contracts_dir.mkdir()
    result = gate_check.evaluate(empty_contracts_dir)
    assert result["decision"] == "deny"
