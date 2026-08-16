---
name: build-with-ratchet
description: Use when the user describes something they want built and wants it built through Ratchet's contract-verified loop instead of a plain delegated goal -- or when the user invokes /build-with-ratchet. Turns their plain-language goal into an approved, executable contract (drafted by you, approved by them in one pass, never written by hand by the human), delegates the build, verifies against that contract yourself, and records what happened. Takes no arguments; the goal comes from the conversation.
---

# build-with-ratchet

Ratchet's library is bundled read-only inside this plugin (`${CLAUDE_PLUGIN_ROOT}/scripts/*.py`) —
it is Python functions and hand-written `assert` blocks, not something to hand a human. This skill
is the layer between "I want to build X" and that library: you draft the contract, the human
approves one pass of it, and you drive the rest of the loop yourself. The human should never need
to open a `.py` file or write a `contract-check` block themselves.

Full mechanism and raw command reference: `${CLAUDE_PLUGIN_ROOT}/README.md`.

## Where code lives vs where state lives

The plugin's code is bundled read-only at `${CLAUDE_PLUGIN_ROOT}/` (its install location) and is
never edited. All contract/change/audit STATE lives in the TARGET project being worked on, under
`ratchet-state/` at that project's root — never inside the plugin:

```
<target project>/
├── ratchet-state/
│   ├── contracts/            # what "done" means, per module (functional/*.md) + quality/FITNESS.json baseline
│   ├── changes/              # work in progress -- each folder's name is its slug; archive/ holds completed ones
│   ├── audit/                # audit sample log (sample-log.md)
│   ├── runs/                 # per-run records/evidence you choose to keep
│   ├── RUNG_STATS.json       # fills in as tasks complete -- never edit by hand
│   └── PROVIDERS.md          # human-owned allowed provider/model list, cheapest first -- edit by hand
```

**First use:** if this project has no `ratchet-state/` directory yet, create it before proceeding:

```bash
mkdir -p ratchet-state/contracts ratchet-state/changes ratchet-state/audit ratchet-state/runs tests/contracts
```

Run every call below from the target project root, never from inside the plugin. Two invocation
shapes, both wired to what the scripts already support (nothing new is invented here):

- **CLI entry points** (only where a script defines `main()` — see `cli_support.py`):
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py" <args>`
- **Library calls**: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 - <<'PY' ... PY` so
  `from scripts.<module> import ...` resolves to `${CLAUDE_PLUGIN_ROOT}/scripts/<module>.py`.

## Before you draft anything: resolve the target

Find (or create, per the first-use step above) the `ratchet-state/` directory in the project the
human is working in. If there is no `ratchet-state/` and you cannot create one (not your project),
say so and stop. Confirm the target files/module the goal touches, so you know whether this is
greenfield (nothing there yet) or brownfield (real behavior to respect).

**Resume check first:** a previous session may have died mid-task. Before drafting anything new,
ask whether the target project has a resumable task waiting, so you never silently start a second,
colliding attempt at work another session already has half-done:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/task_state_store.py" resumable .
```

If it prints any tasks, each one carries `slug`, `progress_path`, and `next_step` — the exact
first unchecked line of that task's checklist. Surface each to the human as *"task `<slug>` is
mid-`<next_step>`, resume or start fresh?"* and get their explicit choice — never a silent
resume, never a silent fresh start.

**Recall learned patterns before drafting:** the project may also carry advisory instincts from
past sessions (`memory/instincts/` — one Markdown file per instinct, created on first `record`, absent on a fresh project).
Read them before drafting a contract:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/memory.py" recall memory/instincts
```

Surface any returned instinct's `pattern` text **verbatim** as advisory context for the goal —
recalled patterns are self-reported context to consider, never a substitute for a passing
contract check (memory is the weakest evidence tier by design, per `memory.py`'s own docstring).
If it returns no entries (fresh project), continue normally.

## Track the loop's phase state (cross-session continuity)

No separate snapshot — the checklist file IS the state. At contract-drafting time (Step 2) you
write `tests/contracts/<slug>.progress.md`, one `- [ ] <step>` line per implementation step, in
the order you'll do them. As each step actually completes, check it off — `mark_step_done` finds
the line whose text matches exactly and raises `ValueError` if no matching unchecked line exists,
so a step that isn't on the checklist (or is already checked) can never be marked done:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 - <<'PY'
from pathlib import Path
from scripts.progress import mark_step_done
mark_step_done(Path("tests/contracts/<slug>.progress.md"), "<exact step text>")
PY
```

A fresh session resumes from the first unchecked line, read directly from the file:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 - <<'PY'
from pathlib import Path
from scripts.progress import first_unchecked_step
print(first_unchecked_step(Path("tests/contracts/<slug>.progress.md")))
PY
```

The statuses this loop used to persist (`generating`/`verifying`/`repairing`/`done`/`stuck`)
need no snapshot anymore: a session that died mid-step simply left that step unchecked. The
repair ladder still runs off `loop_state.next_action` (Step 6) — but nothing writes a
`TaskState` to disk; the checklist is the only resume record.

## Step 1: Understand the goal — at most one clarifying round

State the goal back in one sentence: *"I'll build `<thing>` — it should `<observable behavior>`."*
Ask exactly one clarifying question only if there are genuinely different plausible
interpretations that would produce a different contract; otherwise proceed. Do not run a
multi-round Socratic dialogue here.

If the goal is bigger than 2-4 checks can honestly cover (a whole app, several unrelated
features), decompose it into an ordered list of smaller named changes first, tell the human that
list, and run the rest of this skill once per change.

## Step 2: Draft the contract yourself

Write 2-4 `contract-check` blocks that capture what "done" means for this goal — concrete example
inputs/outputs or invariants, as real Python `assert` statements, the same convention
`${CLAUDE_PLUGIN_ROOT}/scripts/contracts.py` executes. The human does not write these. You do,
from the goal.

- **Greenfield** (nothing exists yet): pick the reference cases that most obviously distinguish
  "works" from "doesn't" — boundary values, the stated examples, one clearly-wrong input if the
  goal implies validation.
- **Brownfield** (changing something real): read the current behavior first, and ground at least
  one check in what it already does today, so the contract doesn't silently redefine existing
  behavior out from under the rest of the project.

Write the draft to `ratchet-state/contracts/functional/<domain>.md` (new domain) or as a delta
inside a change folder scaffolded with `changes.new_change(changes_dir, slug)` (an existing
domain, a bigger change). Do not call `gate_check.approve_contract` yet.

Write the implementation checklist alongside the contract — this file IS the resumable state
(phase-state section above), one `- [ ] <step>` line per implementation step, in order:

```bash
cat > tests/contracts/<slug>.progress.md <<'EOF'
- [ ] <first implementation step>
- [ ] <second implementation step>
- [ ] <...>
EOF
```

## Step 3: Present it once, densely — then get one approval

Show the human, in a single message, both:
1. A plain-English line per check — *"this means: converting 0°C returns exactly 32°F."*
2. The actual contract-check code.

Then ask one direct question: *"Does this match what you want? Reply to approve, or tell me what
to change."* This is the one human touchpoint for the whole loop — it must be dense enough to
approve or correct in one reply, not a form to fill in over several rounds. If they ask for
changes, revise and present once more; do not proceed on an implicit or partial approval.

## Step 4: Approve, pick a rung, delegate

Once approved, scan the contract for dangerous patterns (it gets `exec()`'d on approval and every
verify run), then record its hash as approved:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/security.py" scan-contract ratchet-state/contracts/functional/<domain>.md
```

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 - <<'PY'
from pathlib import Path
from scripts.gate_check import approve_contract
approve_contract(Path("ratchet-state/contracts/functional/<domain>.md"))
PY
```

Then look up the cheapest proven rung for this task class:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 - <<'PY'
from pathlib import Path
from scripts.rung_stats import lookup_starting_rung
print(lookup_starting_rung(
    Path("ratchet-state/RUNG_STATS.json"),
    Path("ratchet-state/PROVIDERS.md"),
    "<task_class>",
))
PY
```

If that returns `None` (cold start — the normal case for a new task shape), pick the cheapest
allowed provider/model from `ratchet-state/PROVIDERS.md` yourself, exactly per this project's own
cost-ladder rule — never ask the human to pick a model or effort level.

Invoke `/use-coding-agent` for the actual build, with the goal stated as: implement against the
approved contract at `<contract_path>`, and its acceptance check stated as: `contracts.run_checks`
on that same path returns `{"passed": true, "failures": []}`. Follow that skill's own procedure
for spawning, driving, and settling the worker — this skill does not reimplement pane-driving.
Check off each implementation step as the worker lands it — `mark_step_done` per the
phase-state section above; a step is only checked when it's genuinely done.

## Step 5: Verify yourself — never the worker's report

Make sure every completed implementation step is checked off before you verify — the verify run
is the final step's proof (phase-state section above).

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 - <<'PY'
from pathlib import Path
from scripts.contracts import run_checks
print(run_checks(Path("ratchet-state/contracts/functional/<domain>.md")))   # you run this; the worker's own claim is never evidence
PY
```

Also run the non-functional layers against whatever files changed:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/security.py" scan-secrets <changed_path> [<changed_path>...]
```

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 - <<'PY'
from pathlib import Path
from scripts import quality, consistency
paths = [Path(p) for p in "<changed_path>".split()]
print(quality.check_ratchet(
    quality.compute_scores(paths),
    quality.load_baseline(Path("ratchet-state/contracts/quality/FITNESS.json")),
))
print(consistency.nonconforming_names(paths))
PY
```

Read the actual diff too, not just the pass/fail — a passing contract check proves the contract
held, not that the diff is sane. If anything in the diff wasn't part of the assigned goal, read it
in full before accepting it.

## Step 6: If it failed, follow the repair order — don't skip to escalating

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 - <<'PY'
from scripts.loop_state import TaskState, next_action
state = TaskState(
    task_id="<id>", contract_ref="<contract_path>", provider="<provider>", model="<model>",
    rung_exhausted_at_top=False, attempts_at_current_rung=0, status="repairing",
)
print(next_action(state))   # "retry_same_rung" | "raise_effort" | "escalate_rung" | "escalate_to_human" | "mark_done"
PY
```

Leave the failing step unchecked until the repair actually lands — then mark it done
(phase-state section above).

Follow whatever it returns, cheapest remedy first, exactly like any other delegated goal. Loop
back to Step 4's delegation with a corrected prompt naming the exact defect found — never a vague
retry.
Re-save the snapshot on every repair attempt — status `repairing`, with the updated
`attempts_at_current_rung` and `rung_exhausted_at_top` (phase-state section above).

## Step 7: Record, archive, audit — then report in plain language

Mark the final step done once verified and archived — or, on escalation, leave it unchecked as
the honest resume point (phase-state section above).

If this task needed a repair and a specific pattern is what got you through it, record a pattern
worth remembering for the next session — same file the recall step above reads
(`memory/instincts/`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/memory.py" record memory/instincts <task_class> "<the pattern that helped>" <evidence_ref>
```

`evidence_ref` must be checkable — a real commit sha or change slug from this session, never a
placeholder (`record` rejects an empty one). Keep the default confidence (0.3) unless the recorded
`pattern` text itself justifies a higher value.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 - <<'PY'
from pathlib import Path
from scripts.rung_stats import record_outcome
record_outcome(Path("ratchet-state/RUNG_STATS.json"), "<task_class>", "<provider>", "<model>", True, 0.0, 0.0)
PY
```

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 - <<'PY'
from pathlib import Path
from scripts.changes import archive_change
archive_change(Path("ratchet-state/changes"), Path("ratchet-state/changes/archive"), "<slug>")   # only if a change folder was scaffolded in Step 2
PY
```

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 - <<'PY'
from pathlib import Path
from scripts import audit
rate = audit.sample_rate(consecutive_clean_passes, risk_flag_count)
audit.log_sample_decision(Path("ratchet-state/audit/sample-log.md"), "<slug>", rate, audit.should_sample(rate, "<slug>"))
PY
```

Cost and latency must be the real, measured numbers from the delegation; if you have no way to
measure them, pass `0.0` explicitly and say so in your report — never invent a plausible-looking
number.

Tell the human, in plain language, no Python: what got built, where, which contract it satisfies,
what it cost, and that it's done — or, on escalation, exactly what failed and at which rung.

## Common mistakes

- Asking the human to write or edit a `contract-check` block directly — draft it yourself, always.
- Presenting the contract over several small messages instead of one dense pass.
- Treating a passing `run_checks` result as proof the whole diff is correct, rather than proof the
  contract held — read the diff.
- Picking a model/effort rung by asking the human, instead of by the cost ladder.
- Writing state into `${CLAUDE_PLUGIN_ROOT}/` (the read-only plugin install) instead of
  `ratchet-state/` in the project being worked on.
- Skipping the non-functional layers because the functional contract passed.
