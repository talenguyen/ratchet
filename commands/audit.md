---
name: audit
description: Record the completed build's outcome in RUNG_STATS.json, archive its change folder, and log the audit sampling decision.
---

Record what happened for the completed build and archive it. All state lives in `ratchet-state/`
at the project root; the plugin code at `${CLAUDE_PLUGIN_ROOT}/` is read-only.

1. **Record the real outcome** in the rung table (task class, provider, model, pass/fail):
   `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "from pathlib import Path; from scripts.rung_stats import record_outcome; record_outcome(Path('ratchet-state/RUNG_STATS.json'), '<task_class>', '<provider>', '<model>', True, 0.0, 0.0)"`
   Cost/latency must be the real measured numbers from the delegation; if you have no way to
   measure them, pass `0.0` explicitly and say so — never invent a plausible-looking number.

2. **Archive the change folder** (only if one was scaffolded):
   `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "from pathlib import Path; from scripts.changes import archive_change; archive_change(Path('ratchet-state/changes'), Path('ratchet-state/changes/archive'), '<slug>')"`

3. **Log the audit sampling decision** for this change:
   `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "from pathlib import Path; from scripts import audit; rate = audit.sample_rate(<consecutive_clean_passes>, <risk_flag_count>); audit.log_sample_decision(Path('ratchet-state/audit/sample-log.md'), '<slug>', rate, audit.should_sample(rate, '<slug>'))"`

4. **Commit** — `git add` the changed files plus the updated `ratchet-state/` files and
   `git commit`. Treat this as a mandatory last step, not optional cleanup.

5. **Report in plain language** what got built, which contract it satisfies, what it cost, the
   audit decision (sampled / not sampled), and the commit — or, if any step failed, exactly what
   failed and at which rung.
