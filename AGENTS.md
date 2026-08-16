# ratchet-v2

Ratchet is a workflow for driving coding agents: no code is written until a
contract test exists and is failing (red), nothing completes unless that contract
is still green and untampered, and every implementation step is dispatched to the
cheapest model that demonstrably works.

This file is the cross-tool entry point — the same loop runs in Claude Code,
Codex, and pi, and each harness has only a thin adapter skill (see `.claude/`,
`.agents/`, `.pi/`). All workflow state is tool-independent and lives under
`ratchet/`.

## Where a fresh session starts

Read `ratchet/plan.md` first: it is the ordered backlog, and `propose` picks the
next work item from it. Then read `ratchet/context/project.md` (the source of
truth about this project) and the one active spec in
`ratchet/context/work-item.md`.

## The core loop

Every work item moves through six steps, in order:

1. **propose** — writes the next item's spec into `ratchet/context/work-item.md`
   and drafts its contract under `ratchet/contracts/<work-item-id>/contract.json`,
   then stops for human review; nothing is implemented yet.
2. **approve** — a human reviews the spec and the contract, and approval makes
   Mechanism 1 structural: the contract is finalized with the sha256 of the
   contract test file plus the approval signature, written to
   `ratchet/contracts/<work-item-id>/contract.json`.
3. **implement** — works through the spec's steps one at a time, resuming from
   the first unchecked checkbox in `ratchet/context/work-item.md`; for each step
   it picks the model from `ratchet/context/models/rung-table.json` (Mechanism 2)
   and appends the outcome to `ratchet/context/models/outcomes.log.jsonl`.
4. **check** — runs the contract test and verifies the done-when evidence the
   completed steps claim, against the contract in
   `ratchet/contracts/<work-item-id>/contract.json`; on failure the item returns
   to `implement`.
5. **audit** — reviews the work and records findings in
   `ratchet/context/findings.md` with durable IDs (`F-01`, `F-02`, ...) and a
   status of `open`, `fixed`, or `closed`.
6. **complete** — the gate: refuses to finish while any P0/P1 finding is open or
   fixed, re-verifies the contract's sha256 sidecar still matches the on-disk
   test file (Mechanism 1 again), then archives the spec to
   `ratchet/history/{features,fixes,rollbacks}/` and updates `ratchet/plan.md`.

## Mechanism 1 — the red-before-green contract (structural)

Mechanism 1 is why Ratchet exists: no code is written until a contract test
exists and is failing, and no work item completes unless the contract's
tamper-evident hash sidecar still matches. It is enforced at two seams, not left
to verbal instruction:

- **The propose → implement boundary.** `implement` is blocked until
  `ratchet/contracts/<work-item-id>/contract.json` exists, records the sha256 of
  the contract test file and its fail-mode evidence, and the on-disk test file's
  hash matches the recorded one. `approve` is what writes that hash, so an
  unapproved item cannot be implemented.
- **The complete gate.** `complete` recomputes the hash of the contract test file
  and refuses to close the item if it no longer matches the sidecar — a modified
  test cannot silently pass.

## Mechanism 2 — the self-tuning cheapest-rung table

Mechanism 2 decides, per step of `implement`, the cheapest model that still
meets the project's pass-rate threshold. It plugs in exactly at the per-step
model-dispatch decision inside `implement`:

- read `ratchet/context/models/rung-table.json` (task class → cheapest
  provider/model with measured pass rate at or above threshold) and start at the
  rung for the step's task class;
- after the step, append one line to `ratchet/context/models/outcomes.log.jsonl`
  (`task_class`, `provider`, `model`, `result`, `cost_usd`, `latency_s`, `ts`);
- re-tune the rung table from accumulated outcomes so the next dispatch starts at
  the cheapest rung that demonstrably works, not the one that was guessed.

The rung-table and outcome-log formats are documented in
`ratchet/context/models/README.md`.

## Files at a glance

| Path | Role |
| --- | --- |
| `ratchet/plan.md` | ordered backlog; `propose` picks the next item from here |
| `ratchet/context/project.md` | source of truth about the project, read every session |
| `ratchet/context/work-item.md` | the ONE active spec |
| `ratchet/context/findings.md` | findings ledger (durable IDs, open/fixed/closed) |
| `ratchet/context/models/rung-table.json` | Mechanism 2 state |
| `ratchet/context/models/outcomes.log.jsonl` | Mechanism 2 append-only outcome log |
| `ratchet/contracts/<id>/contract.json` | Mechanism 1 state (test path, sha256, fail-mode evidence, approval) |
| `ratchet/history/{features,fixes,rollbacks}/` | archived specs, written on `complete` |

No logic lives in this directory; the loop is implemented by the harness adapter
skills, which are thin pointers into the shared `ratchet/` state.
