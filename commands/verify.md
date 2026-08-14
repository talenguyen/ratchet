---
name: verify
description: Verify the current build against the approved contract and the security, quality, and consistency gates — the worker's own claim is never evidence.
---

Verify the current state of the build against the contract and the non-functional gates. All
state lives in `ratchet-state/` at the project root; the plugin code at `${CLAUDE_PLUGIN_ROOT}/`
is read-only.

1. **Resolve the contract path** — the one named in the conversation, or the contract matching
   the most recent active change under `ratchet-state/changes/`.

2. **Run the contract checks yourself** (never the worker's report):
   `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "from pathlib import Path; from scripts.contracts import run_checks; print(run_checks(Path('<contract.md>')))"`
   This must return `{"passed": true, "failures": []}`.

3. **Scan every changed file for secrets** (mandatory, never sampled):
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/security.py" scan-secrets <changed_path> [<changed_path>...]`
   Must return `"decision": "allow"`.

4. **Quality and consistency** on the changed files:
   `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "from pathlib import Path; from scripts import quality, consistency; paths = [Path(p) for p in '<changed_paths>'.split()]; print(quality.check_ratchet(quality.compute_scores(paths), quality.load_baseline(Path('ratchet-state/contracts/quality/FITNESS.json')))); print(consistency.nonconforming_names(paths))"`
   A `"passed": false` / non-empty list means a regression — fix it (or, if this is the first
   run, save the baseline).

5. **Read the diff itself**, not just the pass/fail — a passing check proves the contract held,
   not that the diff is sane. Flag anything outside the assigned goal.

6. **Report in plain language** which checks passed and which failed (with the exact failing
   assertion/pattern), and the contract path used.
