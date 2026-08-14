"""Advisory, session-crossing memory: recalled context for a fresh session, never authoritative.

Gap this closes: design spec section 7 ("state as a reconstructable snapshot") already covers
resuming a *specific stuck task* from contracts/RUNG_STATS/git -- but nothing previously carried
forward a *general, learned pattern* useful for the next, different task once a session closes and
a fresh one opens with no memory of the last one. Comparing against a competing system's
Instincts/Memory Vault surfaced this as a real, concrete gap, not a hypothetical one.

This module is deliberately the weakest evidence tier by construction (design spec section 5:
"asserted" is the floor) -- nothing here gates anything. Only `contracts.run_checks()` and
`gate_check.py` do that. An instinct is self-reported context to consider, never a substitute for
a passing contract-check, and it must never be cited as if it were one.

Mirrors lessons/README.md's own discipline: a corpus that never changes its mind is not being
tested. `contradict_instinct` exists so a later session that finds a recorded pattern wrong can
say so explicitly, rather than the entry silently staying around to mislead the next reader.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CONFIDENCE = 0.3


@dataclass
class Instinct:
    task_class: str
    pattern: str
    evidence_ref: str
    confidence: float
    created_at: str
    contradicted: bool = False


def record_instinct(
    memory_path: Path,
    task_class: str,
    pattern: str,
    evidence_ref: str,
    confidence: float = DEFAULT_CONFIDENCE,
) -> None:
    """Append one instinct.

    `confidence` defaults low (0.3) because this is self-reported context, not a checked result --
    the caller must justify any higher value with something a reader could actually go verify.
    `evidence_ref` must point at something checkable (a commit sha, a change slug, a contract
    path) -- an instinct with nothing behind it but a claim is exactly what this project's own
    evidence ladder (design spec section 5) puts at the bottom; a required non-empty reference at
    least forces the recorder to name what that "asserted"-tier claim is asserted against.
    """
    if not (0.0 <= confidence <= 1.0):
        raise ValueError(f"confidence must be in [0, 1], got {confidence}")
    if not evidence_ref:
        raise ValueError("evidence_ref is required -- an instinct must point at something checkable")

    entries = load_instincts(memory_path)
    entries.append(
        Instinct(
            task_class=task_class,
            pattern=pattern,
            evidence_ref=evidence_ref,
            confidence=confidence,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    )
    _write(memory_path, entries)


def contradict_instinct(memory_path: Path, task_class: str, pattern: str) -> int:
    """Mark all matching, not-yet-contradicted instincts as contradicted. Returns the count marked.

    Matches on exact (task_class, pattern) -- a later session that finds this pattern doesn't
    hold must say so with the same two identifying fields it was recorded under, not a fuzzy guess.
    """
    entries = load_instincts(memory_path)
    marked = 0
    for entry in entries:
        if entry.task_class == task_class and entry.pattern == pattern and not entry.contradicted:
            entry.contradicted = True
            marked += 1
    _write(memory_path, entries)
    return marked


def load_instincts(memory_path: Path) -> list[Instinct]:
    if not memory_path.exists():
        return []
    raw = json.loads(memory_path.read_text(encoding="utf-8"))
    return [Instinct(**item) for item in raw.get("entries", [])]


def recall(memory_path: Path, min_confidence: float = 0.5, limit: int = 6) -> list[Instinct]:
    """What a fresh session should be shown at start: not-contradicted, confident-enough
    instincts, ranked highest confidence first, capped to `limit`.

    This function decides what to *show*, never what to *trust* -- the caller (a fresh session
    reading this at start, per the loop instructions) must still treat every returned entry as
    unverified context, exactly as this module's docstring says.
    """
    entries = [
        e for e in load_instincts(memory_path) if not e.contradicted and e.confidence >= min_confidence
    ]
    return sorted(entries, key=lambda e: e.confidence, reverse=True)[:limit]


def _write(memory_path: Path, entries: list[Instinct]) -> None:
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(
        json.dumps({"entries": [asdict(e) for e in entries]}, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    usage = (
        "usage: memory.py recall <memory.json> [min_confidence] [limit]\n"
        "       memory.py record <memory.json> <task_class> <pattern> <evidence_ref> [confidence]\n"
        "       memory.py contradict <memory.json> <task_class> <pattern>"
    )
    if len(argv) < 3:
        print(json.dumps({"error": usage}))
        return 2

    command, memory_path = argv[1], Path(argv[2])
    rest = argv[3:]

    if command == "recall":
        min_confidence = float(rest[0]) if len(rest) >= 1 else 0.5
        limit = int(rest[1]) if len(rest) >= 2 else 6
        entries = recall(memory_path, min_confidence=min_confidence, limit=limit)
        print(json.dumps({"entries": [asdict(e) for e in entries]}, indent=2))
        return 0

    if command == "record" and len(rest) >= 3:
        task_class, pattern, evidence_ref = rest[0], rest[1], rest[2]
        confidence = float(rest[3]) if len(rest) >= 4 else DEFAULT_CONFIDENCE
        try:
            record_instinct(memory_path, task_class, pattern, evidence_ref, confidence)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}))
            return 2
        print(json.dumps({"recorded": True}))
        return 0

    if command == "contradict" and len(rest) >= 2:
        marked = contradict_instinct(memory_path, rest[0], rest[1])
        print(json.dumps({"marked": marked}))
        return 0

    print(json.dumps({"error": usage}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
