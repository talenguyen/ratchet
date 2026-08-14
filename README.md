# Ratchet — Claude Code plugin

A contract-verified, security/quality/consistency-gated build loop for coding agents. Turns a
plain-language goal into an approved, executable contract (2–4 `contract-check` `assert` blocks),
gates Write/Edit capability on an approved contract, and verifies the build against the contract
plus security, quality, and consistency gates — never against the worker's own report.

## Architecture

For a newcomer's overview of how the pieces fit together — the contract → gate → build → verify
loop, the skill/commands/scripts/hook component layout, the code-vs-state split, and an
end-to-end walkthrough of `/build-with-ratchet` — see [ARCHITECTURE.md](ARCHITECTURE.md).

## Install

This repo is its own marketplace: the root `.claude-plugin/marketplace.json` points at the repo
root itself, so installing from GitHub is two commands:

```bash
claude plugin marketplace add talenguyen/ratchet
claude plugin install ratchet
```

`claude plugin marketplace add talenguyen/ratchet` resolves to
`https://github.com/talenguyen/ratchet` and registers this repository as a marketplace. The
plugin's `PreToolUse` hook (`hooks/hooks.json`) is registered on install: until a contract in the
target project is approved, `Write`/`Edit` are denied with an explanatory message.

## What you get

| Piece | Location | What it does |
|---|---|---|
| Skill | `skills/build-with-ratchet/SKILL.md` | `/build-with-ratchet` — the full loop, human-facing |
| Commands | `commands/contract.md`, `verify.md`, `audit.md` | `/contract` (draft + scan + approve), `/verify` (run the checks yourself), `/audit` (record + archive + commit) |
| Scripts | `scripts/*.py` | The library. `gate_check.py`, `security.py`, and `memory.py` have `main()` CLI entry points; the rest are library functions |
| Hook | `hooks/pretooluse_gate.py` + `hooks/hooks.json` | Denies Write/Edit until an approved contract exists |

## Code vs state: what lives where

- **Code** is bundled read-only at `${CLAUDE_PLUGIN_ROOT}/` (the plugin install location) and is
  never edited. This is also the only place the code lives — nothing is copied into your project.
- **State** lives in the TARGET project being worked on, under `ratchet-state/` at the project
  root:

```
<target project>/
└── ratchet-state/
    ├── contracts/            # approved contract files (functional/*.md) + quality/FITNESS.json baseline
    ├── changes/              # change folders, one per slug; archive/ for completed ones
    ├── audit/                # audit sample log (sample-log.md)
    ├── runs/                 # per-run records/evidence
    ├── RUNG_STATS.json       # empirical rung table — fills in as tasks complete, never hand-edited
    └── PROVIDERS.md          # human-owned allowed provider/model list, cheapest first
```

**First use in a project:** create the state directory before the first contract:

```bash
mkdir -p ratchet-state/contracts ratchet-state/changes ratchet-state/audit ratchet-state/runs
```

## Using it

1. Tell the agent what you want built, or run `/build-with-ratchet`. It drafts the contract,
   shows it to you once in plain language, and only proceeds on your approval.
2. `/contract` — draft, security-scan, and approve a contract (or scaffold a change).
3. The build is delegated; `/verify` runs the contract checks and the security/quality/consistency
   gates yourself — the worker's own claim is never evidence.
4. `/audit` records the measured outcome in `RUNG_STATS.json`, archives the change, logs the audit
   sampling decision, and commits.

## Invocation conventions

Run everything from the target project root. Scripts with a `main()` CLI:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gate_check.py"   ratchet-state/contracts ratchet-state/changes
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/security.py"     scan-contract <contract.md> | scan-secrets <path>...
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/memory.py"       recall|record|contradict <memory.json> ...
```

Library calls (e.g. `approve_contract`, `run_checks`, `record_outcome`, `archive_change`,
`sample_rate`, `next_action`, `new_change`, `parse_providers`):

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "from pathlib import Path; from scripts.contracts import run_checks; print(run_checks(Path('ratchet-state/contracts/functional/<domain>.md')))"
```

## Development / self-test

The bundled tests exercise the scripts in place:

```bash
python3 -m pytest tests/ -v
```

`RATCHET_CONTRACTS_DIR` / `RATCHET_CHANGES_DIR` override the hook's state directories (used by the
tests to isolate from any real project state).
