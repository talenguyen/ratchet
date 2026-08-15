# Ratchet — Claude Code plugin

A contract-verified, security/quality/consistency-gated build loop for coding agents. Turns a
plain-language goal into an approved, executable contract (2–4 `contract-check` `assert` blocks),
gates Write/Edit capability on an approved contract, and verifies the build against the contract
plus security, quality, and consistency gates — never against the worker's own report.

## ⚠️ Status: known limitations (read before relying on this)

An independent adversarial review (2026-08-15) verified the following against the actual code and
runtime behavior -- not assumptions. Read this before installing on anything you depend on.

**The gate is weaker than "structural" implies:**
- `approve_contract()` has no check on who calls it -- the same agent session that will build
  against a contract can approve it itself. The human-approval step is enforced by instruction only.
- `gate_check.evaluate()` never inspects the path being written. One approved contract, anywhere,
  opens Write/Edit for every file in the project (Claude Code) or the whole filesystem the
  session's tools can reach (pi) -- not just the file the contract describes.
- The Claude Code hook (`hooks/pretooluse_gate.py`) has no error handling: malformed input crashes
  it, and a hook that produces no valid decision makes Claude Code fail OPEN (the write proceeds
  unguarded).
- The `pi` gate (`extensions/ratchet-gate.ts` / `lib/gate-logic.mjs`) has two confirmed bugs as of
  commit `12e2e42`: its ratchet-tooling exemption substring-matches the whole command, so appending
  a comment referencing any ratchet script name (e.g. `# see gate_check.py`) exempts an arbitrary
  compound command from the gate entirely; and it blocks every tool call (including `read`, `grep`,
  `ls`) before any contract exists, not just `write`/`edit`/`bash` as documented -- an agent can't
  even read a brownfield codebase to draft an informed contract yet.

**It doesn't ratchet over time:**
- `contracts.run_checks()` runs exactly the one contract passed to it. Nothing re-runs previously
  approved contracts, so a later change can silently break an earlier one's guarantee and nothing
  here will notice.
- Verification never invokes the project's own test suite (`pytest`, `npm test`, etc.) -- only the
  contract's own 2-4 asserts, a regex secret scan, and a naming-convention check.
- `audit.sample_rate()` mathematically decays to 0 after 10 consecutive "clean" passes -- and
  "clean" is driven by quality/consistency checks that (see below) essentially cannot fail. Human
  spot-checking converges to zero.
- `rung_stats.lookup_starting_rung()` locks in a model/provider as "proven" after a single
  successful attempt (`pass_rate = 1.0` from `attempts = 1` already clears the default 0.8
  threshold) -- there is no minimum sample size.

**Brownfield use is not yet safe:**
- Contract-check blocks execute via `exec(block, {"__builtins__": builtins})` -- no fixtures, no
  environment, no dependency setup. Any real module with an environment variable, a DB connection,
  or an import that needs configuration will fail its contract for environmental reasons the agent
  cannot distinguish from a real defect.
- `quality.py` and `consistency.py` never save or load a baseline through the documented skill/
  command flow, so the quality gate always reports a pass, and the consistency gate mines its
  "convention" from the same files it's checking (a new file always conforms to itself).
- Both use Python's `ast.parse()` unconditionally -- they raise on any non-Python file, rather than
  skipping it, in a project that is not pure Python.

**Packaging:** no `LICENSE` file yet -- this repository is not yet legally open source.

**What still holds up:** the tamper-evident approval sidecar (`approve_contract` / SHA-256 hash
match) is real and well-designed; the contract-as-executable-assert idea is sound; the code/state
separation is consistent. Treat this project, today, as a discipline ritual for greenfield,
low-stakes work -- not a security boundary, not a regression guard, and not yet ready to be
installed globally or pointed at a codebase you depend on.

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
