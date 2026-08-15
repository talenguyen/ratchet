---
name: build-with-ratchet
description: Use when the user describes something they want built and wants it built through Ratchet's contract-verified loop instead of a plain delegated goal -- or when the user invokes /skill:build-with-ratchet. Turns their plain-language goal into an approved, executable contract (drafted by you, approved by them in one pass, never written by hand by the human), implements it yourself once approved, verifies against that contract yourself, and records what happened. Takes no arguments; the goal comes from the conversation.
---

# build-with-ratchet

Ratchet's library lives read-only at `$RATCHET_SCRIPTS_ROOT` — this package's own gate extension
resolves and exports that path automatically before every bash call you make, so you never need to
compute it yourself. It is Python functions and hand-written `assert` blocks, not something to hand
a human. This skill is the layer between "I want to build X" and that library: you draft the
contract, the human approves one pass of it, and — because this is a solo `pi` session with no
separate worker to delegate to — you implement and verify the rest of the loop yourself, using your
own `read`/`edit`/`write`/`bash` tools. The human should never need to open a `.py` file or write a
`contract-check` block themselves.

## Where code lives vs where state lives

The package's code is bundled read-only at `$RATCHET_SCRIPTS_ROOT` and is never edited. All
contract/change/audit STATE lives in the TARGET project being worked on, under `ratchet-state/` at
that project's root — never inside the package:

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

This package's gate always allows writes/edits under `ratchet-state/contracts/` and
`ratchet-state/changes/`, and always allows bash calls that invoke Ratchet's own scripts —
drafting or scaffolding a contract can never depend on a contract already being approved. Every
other write, edit, or bash call is denied until an approved contract exists.

**First use:** if this project has no `ratchet-state/` directory yet, create it before proceeding:

```bash
mkdir -p ratchet-state/contracts ratchet-state/changes ratchet-state/audit ratchet-state/runs
```

**Trust this project before your first run, or the gate is silently absent.** This package's gate extension is a project-local resource, and pi only loads project-local resources once the project is trusted. Interactive sessions prompt for that trust the first time; non-interactive modes (`-p`/`--print`, `--mode json`, `--mode rpc`) never prompt and silently skip untrusted resources instead -- meaning the gate does not merely weaken, it does not load at all, and every write/edit/bash call succeeds unchallenged. If you're running this non-interactively (scripted, CI), pass `pi -a` (trust project-local files for this run) explicitly. If you're running interactively, just answer the trust prompt once.

Run every call below from the target project root, never from inside this package. Two invocation
shapes, both wired to what the scripts already support (nothing new is invented here):

- **CLI entry points** (only where a script defines `main()` — see `cli_support.py`):
  `python3 "$RATCHET_SCRIPTS_ROOT/<name>.py" <args>`
- **Library calls**: `PYTHONPATH="$RATCHET_SCRIPTS_ROOT" python3 - <<'PY' ... PY` so
  `from <module> import ...` resolves to `$RATCHET_SCRIPTS_ROOT/<module>.py`.

## Before you draft anything: resolve the target

Find (or create, per the first-use step above) the `ratchet-state/` directory in the project the
human is working in. If there is no `ratchet-state/` and you cannot create one (not your project),
say so and stop. Confirm the target files/module the goal touches, so you know whether this is
greenfield (nothing there yet) or brownfield (real behavior to respect).

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
`$RATCHET_SCRIPTS_ROOT/contracts.py` executes. The human does not write these. You do, from the
goal.

- **Greenfield** (nothing exists yet): pick the reference cases that most obviously distinguish
  "works" from "doesn't" — boundary values, the stated examples, one clearly-wrong input if the
  goal implies validation.
- **Brownfield** (changing something real): read the current behavior first, and ground at least
  one check in what it already does today, so the contract doesn't silently redefine existing
  behavior out from under the rest of the project.

Write the draft to `ratchet-state/contracts/functional/<domain>.md` (new domain) or as a delta
inside a change folder scaffolded with `changes.new_change(changes_dir, slug)` (an existing
domain, a bigger change). Do not call `gate_check.approve_contract` yet.

## Step 3: Present it once, densely — then get one approval

Show the human, in a single message, both:
1. A plain-English line per check — *"this means: converting 0°C returns exactly 32°F."*
2. The actual contract-check code.

Then ask one direct question: *"Does this match what you want? Reply to approve, or tell me what
to change."* This is the one human touchpoint for the whole loop — it must be dense enough to
approve or correct in one reply, not a form to fill in over several rounds. If they ask for
changes, revise and present once more; do not proceed on an implicit or partial approval.

## Step 4: Approve, then implement it yourself

Once approved, scan the contract for dangerous patterns (it gets `exec()`'d on approval and every
verify run), then record its hash as approved:

```bash
python3 "$RATCHET_SCRIPTS_ROOT/security.py" scan-contract ratchet-state/contracts/functional/<domain>.md
```

```bash
PYTHONPATH="$RATCHET_SCRIPTS_ROOT" python3 - <<'PY'
from pathlib import Path
from gate_check import approve_contract
approve_contract(Path("ratchet-state/contracts/functional/<domain>.md"))
PY
```

Approval unlocks your own write/edit/bash capability for this task the moment the gate next checks
it — there is no separate worker to delegate to and no rung to pick before this first attempt: you
are already running at whatever model this session was launched with, and that model is the rung.
Implement the change yourself now, directly, using your own tools.

## Step 5: Verify yourself — the same session that wrote it, named honestly

```bash
PYTHONPATH="$RATCHET_SCRIPTS_ROOT" python3 - <<'PY'
from pathlib import Path
from contracts import run_checks
print(run_checks(Path("ratchet-state/contracts/functional/<domain>.md")))   # you run this; your own prior claim is never evidence
PY
```

Also run the non-functional layers against whatever files changed:

```bash
python3 "$RATCHET_SCRIPTS_ROOT/security.py" scan-secrets <changed_path> [<changed_path>...]
```

```bash
PYTHONPATH="$RATCHET_SCRIPTS_ROOT" python3 - <<'PY'
from pathlib import Path
from quality import check_ratchet, compute_scores, load_baseline
from consistency import nonconforming_names
paths = [Path(p) for p in "<changed_path>".split()]
print(check_ratchet(compute_scores(paths), load_baseline(Path("ratchet-state/contracts/quality/FITNESS.json"))))
print(nonconforming_names(paths))
PY
```

Read the actual diff too, not just the pass/fail — a passing contract check proves the contract
held, not that the diff is sane. If anything in the diff wasn't part of the assigned goal, read it
in full before accepting it. **Name this step's evidence honestly**: because the same session wrote
the diff and is now reading it, this specific check sits at the weakest evidence tier
(`LLM-reviewed`, not `reproduced` or `model-diverse verified`) — the contract/security/quality/
consistency checks above are deterministic scripts and don't share that weakness, but the diff-sanity
read does. Say so if you report a result from this step.

## Step 6: If it failed, follow the repair order — don't skip to escalating

```bash
PYTHONPATH="$RATCHET_SCRIPTS_ROOT" python3 - <<'PY'
from loop_state import TaskState, next_action
state = TaskState(
    task_id="<id>", contract_ref="<contract_path>", provider="<provider>", model="<model>",
    rung_exhausted_at_top=False, attempts_at_current_rung=0, status="repairing",
)
print(next_action(state))   # "retry_same_rung" | "raise_effort" | "escalate_rung" | "escalate_to_human" | "mark_done"
PY
```

There is no fresh worker to re-delegate to — each rung of the ladder is an action on this same
session instead:

- **`retry_same_rung`**: stay in this session, correct your own prompt/plan to name the exact
  defect found, and redo Step 4 against the same contract.
- **`raise_effort`**: stay in this session, raise your own thinking level (`/thinking`) for the
  next attempt, then redo Step 4.
- **`escalate_rung`**: fork this session (`/fork`), switch the fork to a stronger model (`/model`),
  and continue the repair there — this is the only repair step that pays the cost of a model
  switch, and it's deliberate: it only happens after the two cheaper repairs above have already
  failed on this rung.
- **`escalate_to_human`**: report to the human exactly what failed and at which rung — never a
  vague "I'm stuck."

## Step 7: Record, archive, audit — then report in plain language

```bash
PYTHONPATH="$RATCHET_SCRIPTS_ROOT" python3 - <<'PY'
from pathlib import Path
from rung_stats import record_outcome
record_outcome(Path("ratchet-state/RUNG_STATS.json"), "<task_class>", "<provider>", "<model>", True, 0.0, 0.0)
PY
```

```bash
PYTHONPATH="$RATCHET_SCRIPTS_ROOT" python3 - <<'PY'
from pathlib import Path
from changes import archive_change
archive_change(Path("ratchet-state/changes"), Path("ratchet-state/changes/archive"), "<slug>")   # only if a change folder was scaffolded in Step 2
PY
```

```bash
PYTHONPATH="$RATCHET_SCRIPTS_ROOT" python3 - <<'PY'
from pathlib import Path
import audit
rate = audit.sample_rate(consecutive_clean_passes, risk_flag_count)
audit.log_sample_decision(Path("ratchet-state/audit/sample-log.md"), "<slug>", rate, audit.should_sample(rate, "<slug>"))
PY
```

Cost and latency must be the real, measured numbers from this session; if you have no way to
measure them, pass `0.0` explicitly and say so in your report — never invent a plausible-looking
number.

Tell the human, in plain language, no Python: what got built, where, which contract it satisfies,
what it cost, and that it's done — or, on escalation, exactly what failed and at which rung.

## Common mistakes

- Asking the human to write or edit a `contract-check` block directly — draft it yourself, always.
- Presenting the contract over several small messages instead of one dense pass.
- Treating a passing `run_checks` result as proof the whole diff is correct, rather than proof the
  contract held — read the diff, and name that read's weaker evidence tier honestly.
- Trying to "pick a rung" before the first attempt — there is no worker to launch at one; rung
  choice only re-enters the loop at `escalate_rung`.
- Writing state into `$RATCHET_SCRIPTS_ROOT` (the read-only package install) instead of
  `ratchet-state/` in the project being worked on.
- Skipping the non-functional layers because the functional contract passed.
