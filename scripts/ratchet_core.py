"""Approve/verify a Ratchet contract against the project's real pytest run (design spec
2026-08-15-ratchet-reduced-design.md). Contracts are ordinary pytest test files under
tests/contracts/ -- this module never execs contract content itself; pytest does.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

try:
    from scripts.cli_support import emit_decision
except ImportError:
    from cli_support import emit_decision

try:
    from scripts.findings import open_blocking_findings
except ImportError:
    from findings import open_blocking_findings

_NO_TESTS_COLLECTED = 5
_TAIL_CHARS = 4000


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(project_root: Path) -> dict:
    config_path = project_root / ".ratchet" / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"no .ratchet/config.json under {project_root} -- run first-use setup"
        )
    return json.loads(config_path.read_text(encoding="utf-8"))


def approved_sidecar_path(project_root: Path, slug: str) -> Path:
    return project_root / ".ratchet" / "approved" / f"{slug}.sha256"


def is_approved(project_root: Path, contract_path: Path) -> bool:
    sidecar = approved_sidecar_path(project_root, contract_path.stem.removeprefix("test_"))
    if not contract_path.exists() or not sidecar.exists():
        return False
    return sidecar.read_text(encoding="utf-8").strip() == sha256_of(contract_path)


def _command_failure_label(combined: str) -> str | None:
    """Return a label when the combined output shows the test_command itself was unrunnable
    rather than the tests failing (external-standards spec 4.5).

    Python's interpreter reports a missing `-m` target as a bare `No module named <mod>` line
    (no `ModuleNotFoundError:` prefix, no quotes, end of line) -- a genuine pytest failure prints
    `ModuleNotFoundError: No module named 'x'` inside a traceback instead, so the two are
    distinguishable by shape. None = the run is a real pytest pass/fail (or internal error).
    """
    for line in combined.splitlines():
        stripped = line.strip()
        if re.search(r": No module named [A-Za-z_][A-Za-z0-9_.]*$", stripped):
            return stripped
    return None


def run_pytest(cwd: Path, target: str | None = None) -> dict:
    """Run the project's own configured test_command (`.ratchet/config.json`) -- never a
    hardcoded interpreter -- and interpret pytest's own exit codes: 5 = no tests were collected
    at all, 0 = passed, 1 = failed. Other codes (2/3/4) are pytest-internal errors, not a
    functional pass/fail -- callers must not treat them as either.

    Found live while dogfooding on a real project that needs `uv run pytest` (its own managed
    venv) rather than a bare interpreter: a hardcoded `sys.executable -m pytest` cannot see a
    package that only exists inside that project's own environment.

    Failures that mean the command itself is wrong -- the executable doesn't exist
    (FileNotFoundError from the shell-out, reported as exit 127) or the interpreter can't run
    the requested module (a bare `No module named` line) -- come back with a `command_error`
    key so callers can surface them distinctly from a normal test failure.
    """
    config = load_config(cwd)
    args = shlex.split(config["test_command"]) + ["-q"]
    if target:
        args.append(target)
    # PYTHONDONTWRITEBYTECODE: never load cached .pyc files. CPython validates a .pyc by
    # int-second mtime + size, so a same-size rewrite within the same second (as the gate's own
    # tests and workflows do) silently executes STALE bytecode otherwise. Set via the
    # environment, not a CLI flag, so it applies regardless of the configured command's shape
    # (`python3 -m pytest`, `uv run pytest`, or a non-Python test_command it's simply inert for).
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)
    except FileNotFoundError:
        label = f"command not found: {args[0]!r}"
        return {"returncode": 127, "tail": label, "command_error": label}
    combined = (result.stdout + result.stderr)[-_TAIL_CHARS:]
    label = _command_failure_label(combined) if result.returncode != 0 else None
    payload = {"returncode": result.returncode, "tail": combined}
    if label:
        payload["command_error"] = label
    return payload


def approve(project_root: Path, contract_path: Path) -> dict:
    result = run_pytest(project_root, target=str(contract_path))
    if result.get("command_error"):
        # a broken test_command must never be mistaken for "the contract fails as required" --
        # both exit 1, and approving on that would bless a contract nobody actually ran
        return {
            "decision": "deny",
            "reason": (
                f"test_command is not runnable: {result['command_error']} -- fix "
                ".ratchet/config.json before approving anything"
            ),
        }
    if result["returncode"] == _NO_TESTS_COLLECTED:
        return {"decision": "deny", "reason": f"{contract_path} defines no tests -- nothing to be done against"}
    if result["returncode"] == 0:
        return {
            "decision": "deny",
            "reason": (
                f"{contract_path} already PASSES against the current code -- a contract that "
                "passes before the work starts cannot distinguish done from not-done; make it "
                "fail first"
            ),
        }
    if result["returncode"] != 1:
        return {"decision": "deny", "reason": f"pytest error (exit {result['returncode']}): {result['tail']}"}

    slug = contract_path.stem.removeprefix("test_")
    sidecar = approved_sidecar_path(project_root, slug)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(sha256_of(contract_path), encoding="utf-8")
    return {"decision": "allow", "reason": f"approved {contract_path} (currently failing, as required)"}


def verify(project_root: Path, contract_path: Path) -> dict:
    slug = contract_path.stem.removeprefix("test_")
    sidecar = approved_sidecar_path(project_root, slug)
    if not sidecar.exists():
        return {"decision": "deny", "reason": f"no approval on file for {contract_path}"}
    if sidecar.read_text(encoding="utf-8").strip() != sha256_of(contract_path):
        return {"decision": "deny", "reason": "contract changed since approval -- the goalposts moved"}

    full = run_pytest(project_root)
    if full.get("command_error"):
        return {
            "decision": "deny",
            "reason": f"test_command is not runnable: {full['command_error']}",
        }
    if full["returncode"] not in (0,):
        return {"decision": "deny", "reason": f"project test suite failing:\n{full['tail']}"}

    this = run_pytest(project_root, target=str(contract_path))
    if this.get("command_error"):
        return {
            "decision": "deny",
            "reason": f"test_command is not runnable: {this['command_error']}",
        }
    if this["returncode"] != 0:
        return {"decision": "deny", "reason": f"the contract's own test is absent, skipped, or failing:\n{this['tail']}"}

    blocking = open_blocking_findings(project_root / ".ratchet" / "findings.json")
    if blocking:
        labels = ", ".join(f"{f['id']}({f['severity']})" for f in blocking)
        return {
            "decision": "deny",
            "reason": f"blocking findings not cleared: {labels}",
        }

    return {"decision": "allow", "reason": f"{contract_path} passes, full suite passes"}


def main(argv: list[str]) -> int:
    usage = "usage: ratchet_core.py approve|verify <contract_path> [project_root]"
    if len(argv) not in (3, 4):
        print(json.dumps({"decision": "deny", "reason": usage}))
        return 2
    command, contract_arg = argv[1], argv[2]
    project_root = Path(argv[3]) if len(argv) == 4 else Path.cwd()
    contract_path = Path(contract_arg)
    if command == "approve":
        result = approve(project_root, contract_path)
    elif command == "verify":
        result = verify(project_root, contract_path)
    else:
        print(json.dumps({"decision": "deny", "reason": usage}))
        return 2
    return emit_decision(result)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
