# Ratchet v2 — fresh start

This branch is the clean rebuild of Ratchet, replacing the accumulated, half-migrated state on
`main` (two parallel gate mechanisms that were never unified, dead scripts, 16 overlapping spec
documents — see the `ai-autonomous` monorepo's
`docs/superpowers/specs/2026-08-16-ratchet-v3-synthesis-design.md` and the plan that follows it for
the full reasoning).

Kept from the old project, reimplemented clean rather than ported:
1. **Mechanically-enforced red-before-green** — a contract (a real test file) must fail before it can
   be approved, and approval is a tamper-evident hash sidecar. A structural rejection, not an
   instruction.
2. **A self-tuning cheapest-rung model table** — pick the cheapest model with a measured pass rate
   above threshold (minimum sample size enforced) for a task class, self-correcting from real
   recorded outcomes.

Architectural foundation: [ai-blueprint](https://github.com/bradtraversy/ai-blueprint)'s workflow
shape — file-backed, one-work-item-at-a-time, `propose → approve → implement → check → audit →
complete`, with a merge gate that already blocks on file-based conditions rather than on prose
instructions. Chosen after directly cloning and reading six competing projects
(`superpowers`, `openspec`, `mattpocock/skills`, `ecc`, `old-coder`, `ai-blueprint`) and scoring them
against: simplicity to implement cleanly, brownfield-readiness, multi-harness portability, and fit
for the two mechanisms above.

Nothing is built yet — this commit marks the starting point. See the referenced spec and plan for
the full skeleton and task breakdown.
