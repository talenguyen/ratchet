---
name: build-with-ratchet
description: Drive the full Ratchet six-step loop (propose -> approve -> implement -> check -> audit -> complete) for the Claude Code harness, calling scripts/contract.py and scripts/rungs.py by their real signatures against the shared ratchet/ state. Use when the user wants to build something through the contract-verified loop.
---

# build-with-ratchet (Claude Code adapter)

This adapter serves the **Claude Code** harness. The loop body below is shared
verbatim with the `.agents/` (Codex / generic AGENTS.md) and `.pi/` adapters:
there is no invocation difference between harnesses — all three execute bash,
so every script call uses the same `PYTHONPATH=. python3 - <<'EOF'` heredoc
form and the same real functions from `scripts/contract.py` and
`scripts/rungs.py`. Only the frontmatter and title differ. Run every command
below from the project root (the directory containing `ratchet/` and
`scripts/`).

## Before you draft anything: resume check

Read `ratchet/context/work-item.md` and `ratchet/plan.md` first. If
`ratchet/context/work-item.md` already has unchecked steps in its Steps
section AND its contract is approved (Step 0 Contract shows a non-null
approval signature — i.e. `ratchet/contracts/<work-item-id>/contract.json`
has a non-null `approved_by`), stop before drafting anything and ask the
human:

> item <id> is mid-<status>, resume or start fresh?

Use the item's real ID and Status. Then act on the answer: resume only on an
explicit "resume", start fresh only on an explicit "start fresh". Never
silently resume, never silently start something new.

## The six-step loop

One work item at a time, in order: propose -> approve -> implement -> check ->
audit -> complete.

### 1. propose

1. Read `ratchet/plan.md` and take the next unchecked item — the first
   `- [ ]` line, top to bottom. That text is the work item.
2. Write the spec into `ratchet/context/work-item.md` following its
   documented template: Item ID / Type / Status, a one-paragraph Goal, a
   "Step 0: Contract" section, and the implementation Steps as checkboxes
   (`- [ ] Step 1: ...`). The checkboxes are the state machine: one checkbox
   per concrete unit of work.
3. Draft the actual contract test file at
   `ratchet/contracts/<work-item-id>/test_contract.py`: a real pytest file
   that exercises the project code the item will change and FAILS against
   the current code (e.g. the function it tests does not exist yet).
4. Call the red-before-green enforcement point:

```bash
PYTHONPATH=. python3 - <<'EOF'
from pathlib import Path
from scripts.contract import propose_contract
print(propose_contract(Path.cwd(), "<work-item-id>", "ratchet/contracts/<work-item-id>/test_contract.py"))
EOF
```

- `{"decision": "deny", "reason": ...}`: the contract is not red yet — the
  reason says whether the test passes, collects no tests, or pytest errored.
  Fix the contract test so it genuinely fails, then re-run. A deny writes
  nothing, so fix-and-retry is safe.
- `{"decision": "allow", ...}`: `ratchet/contracts/<work-item-id>/contract.json`
  now exists with the test's sha256 and fail-mode evidence, unapproved
  (`approved_by: null`). STOP HERE for human review. Do NOT proceed to
  approve without a human having reviewed the spec and the contract.

### 2. approve

Only after a human has reviewed the spec AND the contract. Use the human's
actual name or handle — ask for it if you don't have it:

```bash
PYTHONPATH=. python3 - <<'EOF'
from pathlib import Path
from scripts.contract import approve_contract
print(approve_contract(Path.cwd(), "<work-item-id>", "<HUMAN'S NAME OR HANDLE>"))
EOF
```

- `approved_by` MUST be the human's name/handle — never the agent's own name.
- On allow, the contract is stamped `approved_by` / `approved_at`; the sha256
  sidecar is fixed at approval time and every later gate re-checks it.
- Distinct denial reasons mean distinct fixes, not retries:
  - "test file changed since propose -- re-propose": the test file drifted
    after propose; re-propose it.
  - "test now passes before approval": someone implemented early; the
    red-before-green proof is gone — go back to propose with a fresh red
    contract.

### 3. implement

For each unchecked step in the Steps section of
`ratchet/context/work-item.md`, in order:

1. **Gate first.** Call:

```bash
PYTHONPATH=. python3 - <<'EOF'
from pathlib import Path
from scripts.contract import can_implement
print(can_implement(Path.cwd(), "<work-item-id>"))
EOF
```

If `{"allowed": False, ...}`, stop and report the reason (no contract / not
approved / contract file changed since approval). Do not implement.

2. **Pick the model.** Before doing the step, call:

```bash
PYTHONPATH=. python3 - <<'EOF'
from pathlib import Path
from scripts.rungs import lookup_starting_rung
entry = lookup_starting_rung(Path("ratchet/context/models/rung-table.json"), "<task_class>")
print(entry)
EOF
```

`<task_class>` is a short label for the step's shape, chosen from the step's
nature (e.g. `mechanical_edit`, `test_writing`, `refactor`, `integration`).
If an entry comes back, use its `provider` and `model` for this step. If it
returns `None`, no rung is proven yet (cold start) — pick a provider/model
manually from the cheapest sensible option; never fabricate a ranking.
`min_pass_rate` and `min_attempts` are optional knobs on this call.

3. **Do the step** at the chosen provider/model. Note the real cost and wall
   time of the step.

4. **Record the outcome** — the real measured numbers:

```bash
PYTHONPATH=. python3 - <<'EOF'
from pathlib import Path
from scripts.rungs import append_outcome
append_outcome(
    Path("ratchet/context/models/outcomes.log.jsonl"),
    task_class="<task_class>",
    provider="<provider>",
    model="<model>",
    result="pass",          # "pass" or "fail" only — anything else raises ValueError
    cost_usd=<measured USD>,
    latency_s=<measured seconds>,
)
EOF
```

5. **Budget check.** Decide whether this step's spend warrants flagging to
   the human before continuing:

```bash
PYTHONPATH=. python3 - <<'EOF'
from pathlib import Path
from scripts.rungs import over_budget
print(over_budget(
    Path("ratchet/context/models/rung-table.json"),
    "<task_class>", "<provider>", "<model>",
    current_cost_usd=<measured USD>,
    current_latency_s=<measured seconds>,
))
EOF
```

If `{"flagged": True, ...}` (cost and/or latency exceeded 3x this rung's
historical average), surface the reason to the human and get their decision
before continuing. `{"flagged": False, "reason": "no baseline yet"}` is a
normal cold-start answer and does not block.

6. **Check off the step** in work-item.md (`- [ ]` -> `- [x]`) only after
   its done-when is met. If the session is interrupted, resume from the
   first unchecked step — never redo checked steps, never skip one.

### 4. check

Run the contract test directly — the same command the gate runs:

```bash
python3 -m pytest -q <test_file_path>
```

`<test_file_path>` is the value of `test_file_path` in
`ratchet/contracts/<work-item-id>/contract.json` — exactly the file
`contract.verify_complete` re-runs (it also re-checks that file's sha256
against the sidecar, so do not edit the test to make it pass). Report the
real evidence: the actual pytest output (exit code, pass/fail counts), not a
claim. Still red -> back to implement; green -> audit.

### 5. audit

Review the diff since propose (spec, contract, implementation). Record every
issue in `ratchet/context/findings.md` in the documented format, next ID in
sequence, one finding per line:

    F-<NN> [<P0|P1|P2>] <open|fixed|closed>: <description>

P0 = blocking, P1 = should fix, P2 = nice to fix. Before complete, every
P0/P1 finding must be fixed (status `fixed`, then re-reviewed to `closed`) or
explicitly accepted-with-reason (`closed` with the reason written in the
line). P2 may stay open. No other route closes a finding.

### 6. complete

1. **Retune the rung table once** so it reflects this item's outcomes:

```bash
PYTHONPATH=. python3 - <<'EOF'
from pathlib import Path
from scripts.rungs import retune_rung_table
retune_rung_table(
    Path("ratchet/context/models/rung-table.json"),
    Path("ratchet/context/models/outcomes.log.jsonl"),
)
EOF
```

Call this exactly once, here — not earlier in the loop.

2. **Run the complete gate:**

```bash
PYTHONPATH=. python3 - <<'EOF'
from pathlib import Path
from scripts.contract import verify_complete
print(verify_complete(Path.cwd(), "<work-item-id>"))
EOF
```

Follow the specific denial reason; do not generic-retry:
- "hash mismatch (tampered)": the contract test file was edited after
  approval. Restore it byte-for-byte, or re-propose a fresh contract.
- "test file removed": restore the test file.
- "contract test still failing": the implementation is not done — back to
  implement.
- "no contract on file" / "malformed contract": contract state is missing or
  broken — back to propose.

3. **Only when it allows AND no open/fixed P0/P1 findings remain** in
   `ratchet/context/findings.md`:
   - Archive the spec: copy `ratchet/context/work-item.md` to
     `ratchet/history/{features,fixes,rollbacks}/` by the item's Type, named
     by item ID (e.g. `ratchet/history/features/W-004.md`).
   - Check off the item in `ratchet/plan.md` (`- [ ]` -> `- [x]`).
   - The next propose starts from the next unchecked plan item.

## Brownfield: adopt

For an EXISTING codebase — before running propose on the first item — do the
following once, up front:

1. **Survey the codebase for real.** List the actual files/modules under the
   project root and note the actual stack (language, test framework, how tests
   are run). Use what you found to fill `ratchet/context/project.md` for real,
   replacing its `<PLACEHOLDER>` blocks with the real project name, stack, and
   conventions. Never copy guesses from elsewhere.
2. **Record the baseline once.** Capture which tests ALREADY fail before
   touching anything (old, unrelated debt):

```bash
PYTHONPATH=. python3 - <<'EOF'
from pathlib import Path
from scripts.baseline import record_baseline
print(record_baseline(
    Path.cwd(),
    "python3 -m pytest -q",
    Path("ratchet/context/baseline.json"),
))
EOF
```

   From then on, this gate tells "a pre-existing failure, not my problem" apart
   from "a regression I just caused" — it denies only when a currently-failing
   test is NOT in the baseline; pre-existing failures never block, and fixing
   one is never a regression. A missing baseline denies loudly ("no baseline
   recorded -- run record_baseline first"), never silently treating the project
   as clean:

```bash
PYTHONPATH=. python3 - <<'EOF'
from pathlib import Path
from scripts.baseline import check_no_new_failures
print(check_no_new_failures(
    Path.cwd(),
    "python3 -m pytest -q",
    Path("ratchet/context/baseline.json"),
))
EOF
```

3. **Choose the contract kind per goal.** Work items that ADD new behavior use
   `propose_contract` as normal (red-before-green, `kind: "new_work"`). Work
   items whose goal is to PIN DOWN existing behavior — a regression guard on
   behavior that already works — use `characterize_contract` instead: it is the
   inverse of propose, requires the capture to currently PASS, and writes
   `kind: "characterization"`:

```bash
PYTHONPATH=. python3 - <<'EOF'
from pathlib import Path
from scripts.contract import characterize_contract
print(characterize_contract(Path.cwd(), "<work-item-id>", "ratchet/contracts/<work-item-id>/test_contract.py"))
EOF
```

   A characterization capture that fails is a wrong capture — re-run the target
   and record what it actually returns, not what you assumed.

4. **Keep the baseline in the loop.** For a brownfield project, run
   `check_no_new_failures` as part of EVERY check step from here on — not just
   the contract's own test — so a regression anywhere in the codebase is caught
   at check time, not at complete.
