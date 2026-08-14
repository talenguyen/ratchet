---
name: contract
description: Draft, security-scan, and approve an executable Ratchet contract for the current goal (drafted by you, approved by the human in one pass).
---

Turn the goal the user stated into a Ratchet contract and get it approved. All state lives in
`ratchet-state/` at the project root; the plugin code at `${CLAUDE_PLUGIN_ROOT}/` is read-only.

1. **First use:** if this project has no `ratchet-state/` directory yet, create it first:
   `mkdir -p ratchet-state/contracts ratchet-state/changes ratchet-state/audit ratchet-state/runs`

2. **Draft the contract yourself** — never ask the human to write Python. Write 2-4
   ` ```contract-check ` fenced blocks (real `assert` statements — the same convention
   `${CLAUDE_PLUGIN_ROOT}/scripts/contracts.py` executes) capturing what "done" means:
   - New domain: write them to `ratchet-state/contracts/functional/<domain>.md` (filename stem =
     the change slug).
   - Existing domain / bigger change: scaffold a change folder first with
     `changes.new_change(Path("ratchet-state/changes"), "<slug>")` and write the delta there.

3. **Scan the contract for dangerous patterns** before approving (it gets `exec()`'d on approval
   and every verify run):
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/security.py" scan-contract <contract.md>`
   It must return `"decision": "allow"`. A `"deny"` means a HIGH-severity finding — fix it before
   proceeding; note any MEDIUM findings returned for the human to judge.

4. **Present it once, densely, and get one approval** — a plain-English line per check plus the
   code, then ask: *"Does this match what you want? Reply to approve, or tell me what to change."*
   Do not approve on an implicit or partial approval; revise and re-present if they ask for changes.

5. **On approval, record the contract's hash as approved:**
   `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "from pathlib import Path; from scripts.gate_check import approve_contract; approve_contract(Path('<contract.md>'))"`

6. **Report** the approved contract path and the plain-language checks. Next steps: delegate the
   build with `/use-coding-agent` (acceptance check: `contracts.run_checks` on the contract path
   returns `{"passed": true, "failures": []}`), then `/verify`, then `/audit`.
