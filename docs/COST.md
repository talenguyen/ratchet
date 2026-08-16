# What building this cost, measured

Every number here was recomputed from the real `pi` session logs at
`~/.pi/agent/sessions/` — the sum of every message record's
`usage.cost.total` field, which `pi` writes itself per API request. Nothing
here is self-reported: a worker's own account of its usage is not evidence
(see lesson 026), which is exactly why the numbers are read from the log
instead.

Three session groups built this repository, end to end:

- **The build** — scaffold through Mechanism 1, Mechanism 2, the three harness
  adapter skills, brownfield, and the F-04 fix (tasks 2–6 of the rebuild,
  plus the fix).
- **The dogfood** — a fresh-session, full-loop run through the real skill
  instructions on a greenfield and a brownfield goal (task 7). This is the
  session that found the two structural bugs the per-task unit tests missed
  (F-04, and the baseline checker's collection-abort misread).
- **The wording cleanup** — the pass that dropped the internal
  `v2`/`ratchet2` version wording, making the product name simply *Ratchet*.

All three ran on **pi / opencode-go / deepseek-v4-flash at high thinking** —
the cheapest rung on that provider, at the highest effort setting, never
escalated. Each session's log contains exactly one `model_change` record
(`opencode-go` / `deepseek-v4-flash`) and one `thinking_level_change` record
(`high`): the cheapest rung was never abandoned mid-build.

| Session group | Turns | Cost (USD) |
|---|---:|---:|
| build (`worktrees/ratchet-v2-build/ratchet-v2`) | 103 | $0.040851 |
| dogfood (`projects/ratchet-v2-dogfood`) | 104 | $0.021232 |
| wording cleanup (`worktrees/ratchet-wording-fix/ratchet-v2`) | 16 | $0.004145 |
| **Total** | **223** | **$0.066228** |

The exact command that produces these numbers (a *turn* is one assistant
message carrying a `usage.cost.total` record):

```bash
python3 - <<'PY'
import json, glob

GROUPS = {
    "build":        "~/.pi/agent/sessions/--root-.ai-autonomous-worktrees-ratchet-v2-build-ratchet-v2--/*.jsonl",
    "dogfood":      "~/.pi/agent/sessions/--root-.ai-autonomous-projects-ratchet-v2-dogfood--/*.jsonl",
    "wording fix":  "~/.pi/agent/sessions/--root-.ai-autonomous-worktrees-ratchet-wording-fix-ratchet-v2--/*.jsonl",
}
for name, pat in GROUPS.items():
    cost = turns = 0
    for f in glob.glob(pat.replace("~", __import__("os").path.expanduser("~"))):
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            msg = r.get("message") or {}
            usage = msg.get("usage") or {}
            total = (usage.get("cost") or {}).get("total")
            if total is not None:
                cost += float(total)
                turns += 1
    print(f"{name:12s} turns={turns:4d} cost=${cost:.6f}")
PY
```

This runs against *your own* logs once you have driven the workflow; a fresh
clone has no `~/.pi/` directory, so the numbers above will not reproduce
elsewhere. They are this build's actual spend, point-in-time, not a live
figure.

## What that means in practice

- **The entire rebuild cost about six and a half cents.** 103 turns to build
  both mechanisms, all three adapters, brownfield, and the F-04 fix; 104 turns
  to dogfood the full loop end to end; 16 turns to clean up the version
  wording.
- **The cheapest rung was sufficient for the whole build** — mechanisms,
  skill prose, test-writing, and even the bug fix were all done on
  `deepseek-v4-flash` at high thinking. No step was ever escalated to a dearer
  model, and the workflow's own rule (start at the bottom rung, raise effort
  before raising model) is what the build itself followed.

## The honest caveat

These are *build* costs — what it took to produce the workflow. They say
nothing about whether running the workflow is worth its overhead, and this
project publishes that measurement too, because hiding it would be the exact
unfalsifiable-claim behavior the gate logic exists to reject.

The matched-pair comparative experiment
(`docs/superpowers/specs/2026-08-16-ratchet-comparative-experiment-results.md`
in the ai-autonomous monorepo; lesson 040 in `lessons/`) ran two small,
single-function, well-specified tasks (`dedupe_emails`, `merge_intervals`)
through the real contract-first loop versus a bare, un-gated arm — identical
task text, same worker/model/effort/rung, a hidden edge-case test written and
committed before either arm ran. **The gated arm cost 7.2x and 8.6x more
($0.00244 vs $0.00034; $0.001884 vs $0.000219) and caught zero extra defects
(0/2 pairs differed: both arms failed the hidden check on pair 1, both passed
on pair 2).** The gate's overhead is real and fixed-ish (drafting the
contract, re-running the full suite); its benefit is conditional on a task
that actually contains a catchable defect the ungated arm would miss.

That is the honest boundary of the numbers in this file too: three session
groups, one operator, one model, one rung, one build. Small `n`, published
anyway — the alternative is asserting this workflow is worth its cost, which
is precisely the kind of claim this project's own mechanisms are built to
reject.
