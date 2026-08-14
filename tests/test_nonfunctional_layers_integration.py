from pathlib import Path

from scripts import consistency, quality, security

RATCHET_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = RATCHET_ROOT / "scripts"


def _our_own_scripts() -> list[Path]:
    return sorted(p for p in SCRIPTS_DIR.glob("*.py") if p.name != "__init__.py")


def test_security_gate_allows_our_own_scripts():
    result = security.security_gate(_our_own_scripts())
    assert result["decision"] == "allow"
    assert result["findings"] == []


def test_quality_first_run_establishes_the_baseline(tmp_path):
    # The quality baseline is project state (ratchet-state/contracts/quality/FITNESS.json in
    # a real project); here it lives under tmp_path so the plugin's own dir stays state-free.
    baseline_path = tmp_path / "contracts" / "quality" / "FITNESS.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    current = quality.compute_scores(_our_own_scripts())
    existing = quality.load_baseline(baseline_path)
    result = quality.check_ratchet(current, existing)
    assert result["passed"] is True
    if existing is None:
        quality.save_baseline(baseline_path, current)
    assert quality.load_baseline(baseline_path) is not None


def test_consistency_our_own_scripts_are_snake_case():
    scripts = _our_own_scripts()
    assert consistency.dominant_naming_convention(scripts) == "snake_case"
    assert consistency.nonconforming_names(scripts) == []
