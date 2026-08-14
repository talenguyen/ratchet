"""Scaffold a change folder (design spec section 3: proposal, delta spec, tasks)."""
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path


def new_change(changes_dir: Path, slug: str) -> Path:
    """Create `changes_dir/slug/` with stub `proposal.md`, `contract-delta.md`, and `tasks.md`.

    No `design.md` is created here -- design spec section 3 only calls for
    one when a change is hard-to-reverse, surprising, and a real tradeoff
    exists, which is a judgment call this function does not make on its own.
    """
    change_dir = changes_dir / slug
    change_dir.mkdir(parents=True, exist_ok=False)
    (change_dir / "proposal.md").write_text(
        f"# Proposal: {slug}\n\n<!-- what this change is for and why -->\n",
        encoding="utf-8",
    )
    (change_dir / "contract-delta.md").write_text(
        f"# Contract delta: {slug}\n\n## ADDED Requirements\n\n"
        "## MODIFIED Requirements\n\n## REMOVED Requirements\n",
        encoding="utf-8",
    )
    (change_dir / "tasks.md").write_text(
        f"# Tasks: {slug}\n\n<!-- each task: rung to try, minimum evidence tier, acceptance check -->\n",
        encoding="utf-8",
    )
    return change_dir


def archive_change(changes_dir: Path, archive_dir: Path, slug: str) -> Path:
    """Move `changes_dir/slug` to `archive_dir/<YYYY-MM-DD>-<slug>` and return the new path.

    Raises `FileNotFoundError` if `changes_dir/slug` does not exist.
    """
    src = changes_dir / slug
    if not src.exists():
        raise FileNotFoundError(f"Change not found: {src}")
    today = date.today().isoformat()
    dst = archive_dir / f"{today}-{slug}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return dst
