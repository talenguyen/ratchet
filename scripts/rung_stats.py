"""Read, update, and query the empirically self-tuning rung table (design spec section 6)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class RungEntry:
    task_class: str
    provider: str
    model: str
    attempts: int
    passes: int
    total_cost_usd: float
    total_latency_s: float
    last_updated: str

    @property
    def pass_rate(self) -> float:
        return self.passes / self.attempts if self.attempts else 0.0

    @property
    def avg_cost_usd(self) -> float:
        return self.total_cost_usd / self.attempts if self.attempts else 0.0


def load(path: Path) -> list[RungEntry]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [RungEntry(**entry) for entry in raw.get("entries", [])]


def save(path: Path, entries: list[RungEntry]) -> None:
    payload = {"entries": [asdict(e) for e in entries]}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def record_outcome(
    path: Path,
    task_class: str,
    provider: str,
    model: str,
    passed: bool,
    cost_usd: float,
    latency_s: float,
) -> None:
    """Append this task's outcome to the matching entry, creating it if new."""
    entries = load(path)
    now = datetime.now(timezone.utc).isoformat()
    for entry in entries:
        if (
            entry.task_class == task_class
            and entry.provider == provider
            and entry.model == model
        ):
            entry.attempts += 1
            entry.passes += 1 if passed else 0
            entry.total_cost_usd += cost_usd
            entry.total_latency_s += latency_s
            entry.last_updated = now
            save(path, entries)
            return
    entries.append(
        RungEntry(
            task_class=task_class,
            provider=provider,
            model=model,
            attempts=1,
            passes=1 if passed else 0,
            total_cost_usd=cost_usd,
            total_latency_s=latency_s,
            last_updated=now,
        )
    )
    save(path, entries)


def lookup_starting_rung(
    rung_stats_path: Path,
    providers_path: Path,
    task_class: str,
    min_pass_rate: float = 0.8,
) -> RungEntry | None:
    """Return the cheapest allowed rung with enough passing evidence for this task class.

    `min_pass_rate` is an operator-tunable knob (design spec section 15
    explicitly disclaims any prescribed methodology constant) — 0.8 is this
    implementation's default, not a methodology claim, and callers may
    override it.

    Returns None when no rung recorded for this task class both clears
    `min_pass_rate` and is currently allowed by `providers_path` — a cold
    start has nothing to look up, and the caller must pick a rung manually
    from the allow-list instead of receiving a fabricated ranking.
    """
    from scripts.providers import allowed_pairs

    allowed = allowed_pairs(providers_path)
    candidates = [
        e
        for e in load(rung_stats_path)
        if e.task_class == task_class
        and (e.provider, e.model) in allowed
        and e.pass_rate >= min_pass_rate
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda e: e.avg_cost_usd)
