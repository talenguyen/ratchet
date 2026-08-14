from pathlib import Path

from scripts import audit


def test_sample_rate_decreases_with_clean_track_record():
    fresh = audit.sample_rate(consecutive_clean_passes=0, risk_flag_count=0)
    seasoned = audit.sample_rate(consecutive_clean_passes=5, risk_flag_count=0)
    assert seasoned < fresh


def test_sample_rate_increases_with_risk_flags():
    low_risk = audit.sample_rate(consecutive_clean_passes=0, risk_flag_count=0)
    high_risk = audit.sample_rate(consecutive_clean_passes=0, risk_flag_count=2)
    assert high_risk > low_risk


def test_sample_rate_is_clamped_between_zero_and_one():
    assert audit.sample_rate(consecutive_clean_passes=0, risk_flag_count=100) == 1.0
    assert audit.sample_rate(consecutive_clean_passes=1000, risk_flag_count=0) == 0.0


def test_should_sample_is_deterministic_for_the_same_seed():
    first = audit.should_sample(0.5, "change-slug-a")
    second = audit.should_sample(0.5, "change-slug-a")
    assert first == second


def test_should_sample_never_samples_at_zero_rate():
    assert audit.should_sample(0.0, "any-seed") is False


def test_should_sample_always_samples_at_one_rate():
    assert audit.should_sample(1.0, "any-seed") is True


def test_log_sample_decision_appends_a_line(tmp_path):
    log_path = tmp_path / "sample-log.md"
    audit.log_sample_decision(log_path, "add-widget", 0.25, True)
    text = log_path.read_text(encoding="utf-8")
    assert "add-widget" in text
    assert "SAMPLED" in text
