# Ratchet

A contract-verified workflow for driving coding agents: **no code is written
until a contract test exists and is failing (red)**, nothing completes unless
that contract is **still green and untampered**, and every implementation step
is dispatched to the **cheapest model that demonstrably works**.

The same loop runs in Claude Code, Codex, and pi — each harness has only a thin
adapter skill (`.claude/`, `.agents/`, `.pi/`). All workflow state is
tool-independent and lives under `ratchet/`. The workflow is driven by the
harness adapter skills; the mechanisms they call are real, stdlib-only Python
in `scripts/` with a 43-test pytest suite.

---

## The claims worth reading

**1. Mechanism 1 is a structural rejection, not an instruction.**

Red-before-green is not a guideline the agent is asked to follow. It is a
program that denies. `scripts/contract.py` refuses to propose a contract whose
test already passes (you cannot distinguish done from not-done), refuses to
approve unless the test is *still* failing at approval time, blocks
`implement` unless the contract is approved *and* the on-disk test file still
hashes to the recorded sha256 sidecar, and refuses to complete the item if the
test file changed after approval — a modified test cannot silently pass.

Enforced at two seams, not left to prose:

- **propose → implement boundary.** `implement` is blocked until
  `ratchet/contracts/<work-item-id>/contract.json` exists, records the sha256
  of the contract test file, and the on-disk file's hash matches. `approve` is
  what writes that hash, so an unapproved item cannot be implemented.
- **complete gate.** `complete` recomputes the hash and refuses to close the
  item if it no longer matches the sidecar.

That is the difference between a gate that denies and a guideline that asks:
the mechanism is in code, exits with a structured `deny` and a reason, and is
re-verified against the same hash at both seams.

**2. Mechanism 2 picks models from measured pass rates, not a guessed ladder.**

Per-step model dispatch reads `ratchet/context/models/rung-table.json`: for a
step's task class, the cheapest provider/model whose *measured* pass rate is
at or above threshold (default 80% over at least 3 recorded attempts), cheapest
by measured average cost. After each step, one line is appended to
`ratchet/context/models/outcomes.log.jsonl`, and `retune_rung_table`
recomputes the table from scratch as a projection of that log — the table is
never an independent record. When nothing qualifies yet, `lookup_starting_rung`
returns `None` and the caller picks manually: a cold start must not fabricate a
ranking. The rung you dispatch to is the rung the log says works, not the one
someone guessed.

**3. Whether this earns its cost is measured, not asserted.**

This project's own honest caveat, published the same way it requires of
everything else: a matched-pair comparative experiment
(`docs/superpowers/specs/2026-08-16-ratchet-comparative-experiment-results.md`
in the ai-autonomous monorepo; lesson 040 in `lessons/`) ran two small,
single-function, well-specified tasks — `dedupe_emails` and `merge_intervals` —
through the real contract-first loop (arm A) and bare with no gate (arm B),
identical task text, same worker/model/effort/rung, with a hidden edge-case
test written and committed before either arm ran. Result: **both arms failed
the hidden check on pair 1 and both passed on pair 2 — a 0/2 defect-catch
difference — while arm A cost 7.2x and 8.6x more** ($0.00244 vs $0.00034 and
$0.001884 vs $0.000219, measured from each arm's real session log, not
self-report).

That is the gate's own unfalsifiable-claim rule applied to the gate itself:
the contract mechanism exists to reject "it works" without evidence, and the
cost caveat is the evidence it does not get to hide behind. The measured
verdict is not that gating is worthless — both bugs this workflow found in
itself (F-04 and the brownfield baseline abort, see
[`CONTRIBUTING.md`](CONTRIBUTING.md)) were found by the loop, not by its unit
tests — it is that on this specific task shape, the gate's 7–9x overhead was
not offset by any measured catch.

## Quickstart

You do not install anything. You adopt the workflow into a project, and drive
it through your harness's adapter skill:

```bash
git clone <this repo> && cd <this repo>
```

1. **Pick your harness** — the adapter skill lives at
   `.claude/skills/build-with-ratchet/SKILL.md` (Claude Code),
   `.agents/skills/build-with-ratchet/SKILL.md` (Codex / generic AGENTS.md), or
   `.pi/skills/build-with-ratchet/SKILL.md` (pi). Invoke it in your harness
   (`/build-with-ratchet` in Claude Code and pi); all three run the identical
   loop.
2. **A fresh session starts by reading** `ratchet/plan.md` (the ordered
   backlog), then `ratchet/context/project.md` (the source of truth about the
   project), then the one active spec in `ratchet/context/work-item.md`.
3. **The loop is six steps, in order**: `propose` (writes the next item's spec
   and drafts its contract test — nothing implemented yet; stops for human
   review) → `approve` (a human reviews; approval finalizes the contract with
   the sha256 sidecar) → `implement` (works the spec's steps one at a time,
   each dispatched to the cheapest rung that demonstrably works) → `check`
   (runs the contract test and the done-when evidence) → `audit` (records
   findings with durable IDs) → `complete` (the gate: refuses to finish with
   open P0/P1 findings, re-verifies the hash sidecar, archives the spec).

The full loop, both mechanisms, and the state file formats are documented in
[`AGENTS.md`](AGENTS.md).

## Files at a glance

| Path | Role |
| --- | --- |
| `AGENTS.md` | the cross-tool entry point — read it for the full loop |
| `.claude/` `.agents/` `.pi/` | thin harness adapter skills (one per harness) |
| `scripts/contract.py` | Mechanism 1 — red-before-green contract + sha256 sidecar |
| `scripts/rungs.py` | Mechanism 2 — self-tuning cheapest-rung table |
| `scripts/baseline.py` | brownfield baseline rule (pre-existing failures vs regressions) |
| `tests/` | the 43-test pytest suite |
| `ratchet/plan.md` | ordered backlog; `propose` picks the next item from here |
| `ratchet/context/project.md` | source of truth about the project |
| `ratchet/context/work-item.md` | the ONE active spec |
| `ratchet/context/findings.md` | findings ledger (durable IDs, open/fixed/closed) |
| `ratchet/context/models/` | Mechanism 2 state (rung table + outcome log) |
| `ratchet/contracts/` | Mechanism 1 state (contract per work item) |
| `ratchet/history/` | archived specs, written on `complete` |

## Status

Honest about maturity: the two mechanisms, the brownfield baseline rule, all
three harness adapters, and the 43-test suite are real and green. The workflow
state is fresh — this is the rebuilt product: `ratchet/plan.md` still lists the
rebuild items unchecked, `ratchet/context/project.md` and `findings.md` are
templates awaiting real content, and the outcome log is empty until the first
real step dispatch. Rough edges: the comparative experiment is one model, one
rung, two task pairs; the adapters cover three harnesses, not every harness
that exists.

## Licence

MIT.
