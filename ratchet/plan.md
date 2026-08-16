# Plan — ordered backlog

This file is the ordered backlog of work items for this project. `propose` reads
it, takes the next unchecked item (the first `- [ ]` entry, top to bottom), and
turns it into the one active spec in `ratchet/context/work-item.md`. A checked
item (`- [x]`) has completed the full loop (propose → approve → implement →
check → audit → complete) and its spec has been archived under `ratchet/history/`.
This file is written only from the loop — `propose` and `complete` are the
writers, never a session by hand.

## Checkbox format

- `- [ ] <work item>` — not yet started; this is what `propose` picks next.
- `- [x] <work item>` — completed (passed the `complete` gate, spec archived).

Keep the format exactly: a dash, a space, a bracket pair, a space, then the item
text — one item per line, ordered top to bottom. Do not reorder or rewrite
completed items.

## Backlog

- [ ] Reimplement Mechanism 1: red-before-green contract rejection + sha256 hash sidecar, written fresh against ratchet/contracts/<work-item-id>/contract.json
- [ ] Reimplement Mechanism 2: rung-table self-tuning (lookup_starting_rung, over_budget) against ratchet/context/models/rung-table.json and outcomes.log.jsonl
- [ ] Write the propose / approve / implement / check / audit / complete skill files, one per harness adapter (Claude Code, pi)
