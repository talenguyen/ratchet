---
name: build-with-ratchet
description: Use when the user describes something they want built and wants it built through Ratchet's contract-verified loop instead of a plain delegated goal -- or when the user invokes /skill:build-with-ratchet. Turns their plain-language goal into an approved, executable contract (drafted by you, approved by them in one pass, never written by hand by the human), implements it yourself once approved, verifies against that contract yourself, and records what happened. Takes no arguments; the goal comes from the conversation.
---

# build-with-ratchet

A contract is now an ordinary `pytest` test file under `tests/contracts/` in the target project —
not a private markdown format. Verification runs the project's real test command. Approval requires
you to actually confirm through your own UI, not the agent's say-so.

## First use

If the target project has no `.ratchet/` yet:

```bash
mkdir -p .ratchet/approved tests/contracts
cat > .ratchet/config.json <<'EOF'
{"test_command": "python3 -m pytest"}
EOF
```

Adjust `test_command` to whatever the project actually uses (`npm test`, `go test ./...`, etc.) —
`ratchet_core.py` shells out to exactly this string, so it must be correct for this project.

## Step 1: Understand the goal — at most one clarifying round

Same as always: state the goal back in one sentence, ask one clarifying question only if genuinely
needed, decompose if it's bigger than one contract can honestly cover.

## Before you draft: resume or start fresh

A previous session may have died mid-task. Check before drafting anything new, so you never
silently start a second, colliding attempt at work another session already has half-done:

```bash
python3 "$RATCHET_SCRIPTS_ROOT/task_state_store.py" resumable .
```

If it prints any tasks, each one carries `slug`, `progress_path`, and `next_step` — the exact
first unchecked line of that task's checklist. Surface each to the human as *"task `<slug>` is
mid-`<next_step>`, resume or start fresh?"* and get their explicit choice — never a silent
resume, never a silent fresh start.

## Before you draft: recall learned patterns

The project may also carry advisory instincts from past sessions (`memory/instincts/` — one Markdown file per instinct,
created on first `record`, absent on a fresh project). Read them before drafting a contract:

```bash
python3 "$RATCHET_SCRIPTS_ROOT/memory.py" recall memory/instincts
```

Surface any returned instinct's `pattern` text **verbatim** as advisory context for the goal —
recalled patterns are self-reported context to consider, never a substitute for a passing
verify (memory is the weakest evidence tier by design, per `memory.py`'s own docstring). If it
returns no entries (fresh project), continue normally.

## Track the loop's phase state

No separate snapshot — the checklist file IS the state. At contract-drafting time (Step 2) you
write `tests/contracts/<slug>.progress.md`, one `- [ ] <step>` line per implementation step, in
the order you'll do them. As each step actually completes, check it off — `mark_step_done` finds
the line whose text matches exactly and raises `ValueError` if no matching unchecked line exists,
so a step that isn't on the checklist (or is already checked) can never be marked done:

```bash
PYTHONPATH="$RATCHET_SCRIPTS_ROOT" python3 - <<'PY'
from pathlib import Path
from progress import mark_step_done
mark_step_done(Path("tests/contracts/<slug>.progress.md"), "<exact step text>")
PY
```

A fresh session resumes from the first unchecked line, read directly from the file:

```bash
PYTHONPATH="$RATCHET_SCRIPTS_ROOT" python3 - <<'PY'
from pathlib import Path
from progress import first_unchecked_step
print(first_unchecked_step(Path("tests/contracts/<slug>.progress.md")))
PY
```

The statuses this loop used to persist (`generating`/`verifying`/`repairing`/`done`/`stuck`)
need no snapshot anymore: a session that died mid-step simply left that step unchecked. The
repair ladder still runs off `loop_state.next_action` (Step 7) — but nothing writes a
`TaskState` to disk; the checklist is the only resume record.

## Step 2: Draft the contract as a real test

Write `tests/contracts/test_<slug>.py` — an ordinary test file in the project's actual test
framework, importing the real module it concerns. This file is drafted by you, never by the human.
Writing here never depends on an approval existing yet (the gate's bootstrap exemption covers this
directory unconditionally).

- **Greenfield**: pick the reference cases that most obviously distinguish "works" from "doesn't."
- **Brownfield**: import and exercise the actual existing module — this test runs with the
  project's real fixtures, environment, and dependencies, not a bare sandbox, so it can actually
  assert against real behavior.

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

Same as always: plain-English line per case, then the actual test code, then one direct question.
Revise and re-present on any requested change; never proceed on an implicit approval.

## Step 4: Approve — this step cannot be done by you alone

```bash
python3 "$RATCHET_SCRIPTS_ROOT/ratchet_core.py" approve tests/contracts/test_<slug>.py
```

Running this will pause for your own confirmation dialog before it does anything — you did not
approve this in the chat message above; that was only the presentation. The confirmation you are
about to answer is the actual approval. If the contract already passes before any implementation
exists, this command denies and tells you to make it fail first — go back to Step 2.

## Step 5: Implement

Check off each implementation step as you land it — `mark_step_done` per the phase-state
section above; a step is only checked when it's genuinely done.

Once approved, you have write/edit/bash capability for this task (confined to this project's own
root — writes outside it are never allowed by this gate, approved or not). Implement the change
yourself now, directly.

## Step 6: Verify — the full suite, not just this contract

Make sure every completed implementation step is checked off before you verify — the verify run
is the final step's proof (phase-state section above).

```bash
python3 "$RATCHET_SCRIPTS_ROOT/ratchet_core.py" verify tests/contracts/test_<slug>.py
```

This re-runs the **entire** test suite, not just this contract — every previously approved contract
is an ordinary test file too, so it is re-checked for free. A regression anywhere is caught here,
not just in the change you were just asked to make.

Secret scan the changed files, if `gitleaks` is installed:

```bash
if command -v gitleaks >/dev/null; then
  gitleaks detect --no-git -v --source <changed_path>
else
  echo "gitleaks not installed -- secret scan SKIPPED (not silently passed)"
fi
```

Read the actual diff too — a passing verify proves the contract and the rest of the suite held, not
that the diff is free of anything out of scope.

## Step 7: If it failed, follow the repair order

Leave the failing step unchecked until the repair actually lands — then mark it done
(phase-state section above).

Same repair ladder as before (`retry_same_rung` → `raise_effort` → `escalate_rung` via `/fork` +
`/model` → `escalate_to_human`) — unchanged by this redesign; see `loop_state.py`.

## Step 8: Commit — mandatory, not optional cleanup

Mark the final step done once verified — or, on escalation, leave it unchecked as the honest
resume point (phase-state section above).

If this task needed a repair and a specific pattern is what got you through it, record a pattern
worth remembering for the next session — same file the recall step above reads
(`memory/instincts/`):

```bash
python3 "$RATCHET_SCRIPTS_ROOT/memory.py" record memory/instincts <task_class> "<the pattern that helped>" <evidence_ref>
```

`evidence_ref` must be checkable — a real commit sha or change slug from this session, never a
placeholder (`record` rejects an empty one). Keep the default confidence (0.3) unless the recorded
`pattern` text itself justifies a higher value.

Once `verify` returns `allow`, commit the contract test file plus the implementation together:

```bash
git add tests/contracts/test_<slug>.py <implementation files>
git commit -m "<what this change does>"
```

Do this before moving on to the next change in your decomposition. Leaving verified work
uncommitted is not a smaller version of finishing it.

## Step 9: Report in plain language

What got built, which contract (now a real test file) it satisfies, what the full suite looked like
before and after, and that it's done — or, on escalation, exactly what failed.

## Common mistakes

- Trying to approve a contract yourself without the human's confirm dialog actually appearing —
  if `ratchet_core.py approve` returns instantly with no prompt, something is wrong; stop and say
  so, don't treat that as approval.
- Writing the contract anywhere other than `tests/contracts/` — the gate's bootstrap exemption is
  scoped to that exact directory.
- Treating `verify`'s pass as proof the diff is sane, rather than proof the contract plus the rest
  of the suite held.
- Writing outside the project root — this gate denies that unconditionally, approved or not.
- Moving on to the next change in a decomposition before committing the current one.
