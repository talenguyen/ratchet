# Contributing

Two contribution surfaces are open, and one is closed.

**Open: harness adapters.** An adapter teaches a different coding harness how to
run the same six-step loop, following the pattern the three existing adapters
already establish.

**Closed: the core gate logic.** `scripts/contract.py` (Mechanism 1) and
`scripts/rungs.py` (Mechanism 2) are owned. Issues and findings are very
welcome; PRs that restructure the gate logic generally are not, because its
invariants were each paid for by a bug that was actually found, and the
reasoning lives in the git history and the lessons that record those bugs.

---

## Writing a harness adapter — the pattern to copy

The loop is tool-independent: all workflow state lives under `ratchet/`, and
each harness runs the loop through a thin skill folder that calls
`scripts/contract.py` and `scripts/rungs.py` by their real signatures. Three
adapters exist and are the template:

- `.claude/skills/build-with-ratchet/SKILL.md` — Claude Code
- `.agents/skills/build-with-ratchet/SKILL.md` — Codex / generic AGENTS.md
- `.pi/skills/build-with-ratchet/SKILL.md` — pi

Read all three before writing a fourth. The loop body is shared **verbatim**
across them — there is no invocation difference between harnesses: every
harness executes bash, so every script call uses the same
`PYTHONPATH=. python3 - <<'EOF'` heredoc form against the same real functions.
Only the frontmatter and the title differ. A new adapter should:

- implement the six steps (propose → approve → implement → check → audit →
  complete) by calling the real functions in `scripts/contract.py` and
  `scripts/rungs.py`, never by re-implementing their logic;
- preserve the resume discipline: if `ratchet/context/work-item.md` has
  unchecked steps and an approved contract, stop and ask the human
  "resume or start fresh?" — never silently resume, never silently restart;
- keep every gate callable as `contract.py` / `rungs.py` functions return
  structured `decision`/`allowed` results, so the mechanism stays a program
  that denies rather than a guideline that asks.

If your harness cannot enforce a step mechanically (for example it cannot
verify a process actually ran), say so in the skill and fail closed — never
report `allowed` on a check you did not run.

## Why the gate logic is closed — the F-04 story

The most instructive finding this project has received so far is F-04, and it
is exactly why `scripts/contract.py` is not open to casual PRs:

> `approve_contract` was not kind-aware. Task 6 of the rebuild added
> `characterize_contract` — a brownfield capture that records *already-true*
> behavior and therefore must currently **pass** — but it was never wired into
> Task 3's `approve_contract`, which unconditionally denied any contract whose
> test passed at approval time. The rule was correct for `new_work`
> (red-before-green) and wrong for `characterization`: **every
> characterization contract was permanently unapprovable through the real
> gate.**

The bug was found only by a fresh-session dogfood (Task 7) that drove the
actual skill instructions on a brownfield goal. Both prior task suites were
individually green — 43 and 40 passing respectively — yet neither caught it,
because Task 6's tests exercised `characterize_contract` in isolation and never
called `approve_contract` afterward. The fix (kind-aware approval, commit
`b8cfa84`) was itself delegated as a new task, verified with three new tests,
and merged only when the full suite passed (43 tests).

The lesson generalizes: a change that looks local — say, relaxing one check in
`approve_contract` — silently changes the invariant at the other seam, because
the *complete* gate re-verifies the same sha256 sidecar, and the approval-time
expectation now differs by contract kind (`new_work` must still fail;
`characterization` must still pass). The invariants of this gate are paid for
by bugs that were actually found in the field; they are not negotiable by
review.

## Testing rules

The test suite is pytest:

```bash
python3 -m pytest tests -q
```

**43 tests pass as of this writing** — run the suite yourself before and after
any change; that number is a moving target.

1. **Run the full suite, not just your new test file.** The two real bugs this
   rebuild's dogfood found (F-04 above, and the brownfield baseline checker
   misreading a full collection abort as "zero new failures") were both
   invisible to isolated per-file runs: each task's own tests passed while the
   seam between two tasks' work was broken. If you changed a script, the
   cheapest honest check is the whole `tests/` directory, because the
   cross-task bugs that actually happened here did not announce themselves in
   the file they were in.
2. **Test the entry point, not the internal.** An assertion that calls a
   private helper directly leaves the public function free to disconnect from
   the behavior it promises with every test still green. Drive the public
   functions (`propose_contract`, `approve_contract`, `can_implement`,
   `verify_complete`, `lookup_starting_rung`, `retune_rung_table`) the way the
   skill files do.
3. **Every new assertion must fail under mutation.** Break the behaviour it
   protects, record the non-zero (or denied) result, restore, confirm the
   assertion fails when the behaviour is gone. A test that passes both before
   and after is a defect, not coverage.
4. **Use `tmp_path` fixtures; never write into the repo tree.** Tests must
   leave the working tree byte-identical. The gate logic is hash-based —
   a stray file written during a test would corrupt exactly the invariant the
   tests exist to protect.

## Reporting a finding

The most valuable issues name a **specific defect and how to reproduce it**.
The findings that improved this project most were exactly of that shape:

- "`approve_contract` denies every characterization contract even though the
  capture still passes" — reproduced by proposing a characterization contract
  and calling `approve_contract`; the real F-04, fixed by commit `b8cfa84`.
- "`check_no_new_failures` reports zero new failures when pytest aborts
  collection entirely" — reproduced by introducing a collection-level error
  after recording a baseline; the real second bug from the same dogfood.

A good report for this project looks like: the function, the input that
triggers the wrong result, the expected `decision`/`reason`, and the actual
one. If you can reproduce a tamper scenario that passes the gate — a contract
test edited after approval that still reaches `allow` — that is a P0: report
it with the exact edit and the exact commands.

## Not accepted

Rewriting the gate logic to be "cleaner" or "more flexible" without a
reproduced defect. The gate is deliberately small, stdlib-only, and
deliberately strict. If it denies something, the correct response is a
finding with a reproduction, not a relaxed invariant.
