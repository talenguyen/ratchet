from pathlib import Path

from scripts import providers

FIXTURE = Path(__file__).parent / "fixtures" / "sample_providers.md"


def test_parse_providers_reads_rows():
    entries = providers.parse_providers(FIXTURE)
    assert {"provider": "opencode-go", "model": "deepseek-v4-flash", "allowed": True} in entries
    assert {"provider": "opencode-go", "model": "qwen3.7-plus", "allowed": True} in entries
    assert {"provider": "legacy-go", "model": "old-model", "allowed": False} in entries


def test_allowed_pairs_excludes_disallowed_rows():
    pairs = providers.allowed_pairs(FIXTURE)
    assert ("opencode-go", "deepseek-v4-flash") in pairs
    assert ("legacy-go", "old-model") not in pairs


def test_parse_providers_rejects_file_without_header(tmp_path):
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("just some prose, no table here\n", encoding="utf-8")
    try:
        providers.parse_providers(bad_file)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "no '| Provider | Model | Allowed |' header row found" in str(exc)
