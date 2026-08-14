"""Parse PROVIDERS.md's allowed-provider table into structured data."""
from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict


class ProviderEntry(TypedDict):
    provider: str
    model: str
    allowed: bool


_ROW_RE = re.compile(
    r"^\|\s*(?P<provider>[^|]+?)\s*\|\s*(?P<model>[^|]+?)\s*\|\s*(?P<allowed>[^|]+?)\s*\|\s*$"
)


def parse_providers(path: Path) -> list[ProviderEntry]:
    """Parse the `| Provider | Model | Allowed |` table in a PROVIDERS.md file.

    Skips the header row and the markdown `---` separator row. Raises
    ValueError if no header row is found, or if the header exists but no
    data rows follow it — an empty allow-list is a config error, not a
    valid empty state.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[ProviderEntry] = []
    seen_header = False
    for line in lines:
        match = _ROW_RE.match(line.strip())
        if not match:
            continue
        provider = match.group("provider").strip()
        model = match.group("model").strip()
        allowed_raw = match.group("allowed").strip().lower()
        if provider.lower() == "provider" and model.lower() == "model":
            seen_header = True
            continue
        if set(provider) <= {"-", ":"} or set(model) <= {"-", ":"}:
            continue  # markdown separator row, e.g. |---|---|---|
        entries.append(
            ProviderEntry(provider=provider, model=model, allowed=allowed_raw == "yes")
        )
    if not seen_header:
        raise ValueError(f"{path}: no '| Provider | Model | Allowed |' header row found")
    if not entries:
        raise ValueError(f"{path}: no provider rows found under the header")
    return entries


def allowed_pairs(path: Path) -> set[tuple[str, str]]:
    """Return the set of (provider, model) pairs marked allowed."""
    return {(e["provider"], e["model"]) for e in parse_providers(path) if e["allowed"]}
