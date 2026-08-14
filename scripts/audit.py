"""Audit sampling (design spec section 10, human touchpoint 3): spot-check a fraction of
completed changes rather than reviewing every one. Security-layer checks are exempt --
they are always 100%-gated (spec section 3.2), never subject to this sampling rate.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path


def sample_rate(
    consecutive_clean_passes: int,
    risk_flag_count: int,
    base_rate: float = 0.2,
    decay_per_clean_pass: float = 0.02,
    boost_per_risk_flag: float = 0.15,
) -> float:
    """Sample rate falls as a domain's track record grows and rises with risk flags.

    All four numeric parameters are operator-tunable knobs (design spec section 15
    explicitly disclaims any prescribed methodology constant) -- these defaults are this
    implementation's starting point, not a methodology claim.
    """
    rate = base_rate - (decay_per_clean_pass * consecutive_clean_passes) + (
        boost_per_risk_flag * risk_flag_count
    )
    return max(0.0, min(1.0, rate))


def should_sample(rate: float, seed: str) -> bool:
    """Deterministic, reproducible sampling decision -- given the same rate and seed, this
    always returns the same answer, so an audit decision can be recomputed and verified
    later rather than relying on unrepeatable randomness.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    fraction = int(digest[:8], 16) / 0x100000000
    return fraction < rate


def log_sample_decision(log_path: Path, slug: str, rate: float, sampled: bool) -> None:
    """Append one line to the audit sample log (design spec section 11: audit/sample-log.md)."""
    timestamp = datetime.now(timezone.utc).isoformat()
    outcome = "SAMPLED" if sampled else "not sampled"
    line = f"- {timestamp} `{slug}` rate={rate:.3f} -> {outcome}\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)
