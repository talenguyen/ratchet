"""Security invariant scanning (design spec section 3.2): mandatory, 100%-gated, never sampled."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from scripts.cli_support import emit_decision
except ImportError:
    from cli_support import emit_decision

# Shared by the secret scanner below and the contract-check `hardcoded_secret` finding so the
# two can never drift apart. The compound alternatives matter: plain `\bsecret\b` cannot match
# `aws_secret_access_key` or `secret_key` (the underscore is a word char, so there is no word
# boundary before the suffix), which is exactly how a real AWS secret value slips past a naive
# `password|secret|token` alternation.
_ASSIGNED_SECRET_RE = re.compile(
    r"(?i)\b(?:password|secret|token|api[_-]?key|"
    r"(?:aws[_-]?)?(?:secret|access)[_-]?(?:secret|access)?[_-]?key|"
    r"client[_-]?secret|(?:auth|refresh|access|bearer)[_-]?token)"
    r"\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
)

_PATTERNS: dict[str, re.Pattern] = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_pat": re.compile(r"\bghp_[0-9A-Za-z]{36}"),
    "github_fine_grained_pat": re.compile(r"\bgithub_pat_[0-9A-Za-z_]{22,}"),
    "slack_token": re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}"),
    "stripe_secret_key": re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{24}"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}"),
    "generic_assigned_secret": _ASSIGNED_SECRET_RE,
    "private_key_header": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def scan_for_secrets(path: Path) -> list[dict]:
    """Return one finding per matched pattern per line, with the pattern name and line number."""
    findings: list[dict] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line_no, line in enumerate(text.splitlines(), start=1):
        for name, pattern in _PATTERNS.items():
            if pattern.search(line):
                findings.append({"pattern": name, "path": str(path), "line": line_no})
    return findings


def security_gate(paths: list[Path]) -> dict:
    """Deny if any finding exists across any path -- this gate is never sampled (spec section 3.2)."""
    all_findings: list[dict] = []
    for path in paths:
        all_findings.extend(scan_for_secrets(path))
    if all_findings:
        return {"decision": "deny", "findings": all_findings}
    return {"decision": "allow", "findings": []}


# --- Contract-check risk scanning ---------------------------------------------------------------
#
# A `contract-check` block is markdown-embedded Python that `contracts.run_checks()` executes via
# `exec()` on every approval and every future verify run -- so the contract file is itself a
# code-execution surface, not just a source of possible false results. Nothing previously scanned
# it before `gate_check.approve_contract()` trusted it. Heuristic, regex-based, and deliberately
# narrow: absence of a finding is not proof of safety, and every match still needs a human read
# before it changes an approval decision -- this never silently downgrades or auto-fixes (lesson
# 020's mistake, generalized).

_RISK_PATTERNS: dict[str, dict] = {
    "destructive_rm_rf": {
        # Requires *both* a recursive-ish and a force-ish flag within a bounded window, in any
        # order and any spelling: "rm -rf /", ['rm', '-fr', '/'], "rm -r -f /", and the GNU
        # long forms "rm --recursive --force /" all match, as do the same string inside
        # os.system()/os.popen() (the Python-native shell-out bypasses of this gate). Split
        # short flags and long flags were both realistic false negatives of the old single-token
        # alternation.
        "pattern": re.compile(
            r"\brm\b(?=[^\n;]{0,80}(?:-[a-zA-Z]*[rR]|--[a-zA-Z]*[rR]ecursive))"
            r"(?=[^\n;]{0,80}(?:-[a-zA-Z]*[fF]|--[a-zA-Z]*[fF]orce))"
        ),
        "severity": "high",
        "why": "recursive force-delete inside code that gets exec()'d on approval and every verify run",
    },
    "destructive_shutil_rmtree": {
        # Python-native equivalent of "rm -rf": no shell involved, so no 'rm' token for the
        # pattern above to see, but the destructive effect is identical. A variable target is
        # just as destructive as a literal one (it deletes a whole tree), so no literal-only
        # carve-out.
        "pattern": re.compile(r"\bshutil\.rmtree\s*\("),
        "severity": "high",
        "why": "Python-native recursive delete (shutil.rmtree) -- the direct 'rm -rf' equivalent inside exec()'d contract code",
    },
    "file_deletion": {
        # Single-file deletion has plausible legitimate cleanup uses inside a contract-check
        # (unlike recursive force-delete), so it surfaces as MEDIUM for a human read rather
        # than blocking approval outright.
        "pattern": re.compile(r"\bos\.(?:remove|unlink)\s*\(|\.unlink\s*\("),
        "severity": "medium",
        "why": "deletes a specific file from inside exec()'d contract code -- may be legitimate cleanup, but the target deserves a human read",
    },
    "raw_disk_write": {
        "pattern": re.compile(r"\bdd\s+if="),
        "severity": "high",
        "why": "raw block-device write",
    },
    "pipe_remote_to_shell": {
        "pattern": re.compile(r"\b(curl|wget)\b[^\n]*\|\s*\w*(sh|bash|zsh)\b"),
        "severity": "high",
        "why": "fetches remote content and pipes it directly into a shell",
    },
    "dynamic_exec_of_fetched_content": {
        # os.system() of fetched content is the shell-out sibling of eval/exec of fetched
        # content: same remote-code-execution effect, previously a false negative.
        "pattern": re.compile(r"\b(eval|exec|os\.system)\s*\(\s*\w*(requests\.|urlopen|urllib)"),
        "severity": "high",
        "why": "executes network-fetched content dynamically (eval/exec, or os.system of fetched text)",
    },
    "sensitive_path_write": {
        "pattern": re.compile(r"['\"]~?/?\.(ssh|aws)/|['\"]\/etc\/"),
        "severity": "high",
        "why": "targets a sensitive credential or system path",
    },
    "hardcoded_secret": {
        "pattern": _ASSIGNED_SECRET_RE,
        "severity": "medium",
        "why": "hardcoded credential-shaped literal inside a contract-check block",
    },
    "outbound_network_call": {
        "pattern": re.compile(r"\b(requests\.(get|post|put|patch|delete)|urllib\.request\.urlopen|http\.client\.)"),
        "severity": "medium",
        "why": "outbound network call from inside a contract-check -- confirm the target is intended, not exfiltration",
    },
}


def scan_contract_check_risk(source: str) -> list[dict]:
    """Scan one contract-check block's raw source text for patterns dangerous to exec()
    unreviewed. Line-based, like `scan_for_secrets`, so findings point at an exact location.
    """
    findings: list[dict] = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        for name, spec in _RISK_PATTERNS.items():
            if spec["pattern"].search(line):
                findings.append({
                    "pattern": name,
                    "severity": spec["severity"],
                    "line": line_no,
                    "why": spec["why"],
                })
    return findings


def scan_contract_file_risk(contract_path: Path) -> list[dict]:
    """Scan every ```contract-check block in a contract file. Imports `contracts` lazily so the
    two modules don't form a hard import-order dependency at module load time. Tries the
    package-qualified import first (how pytest imports this module as `scripts.security`), then
    falls back to a sibling import (how this file resolves it when run directly as
    `python3 security.py`, where only its own directory -- not its parent -- is on `sys.path`).
    """
    try:
        from scripts.contracts import extract_checks
    except ImportError:
        from contracts import extract_checks

    findings: list[dict] = []
    for block in extract_checks(contract_path):
        findings.extend(scan_contract_check_risk(block))
    return findings


def contract_approval_gate(contract_path: Path, project_root: Path | None = None) -> dict:
    """Decide whether a contract file is safe to approve.

    Denies only on a HIGH-severity finding -- MEDIUM findings (e.g. a hardcoded-looking secret or
    an outbound network call, both of which have real legitimate uses in a contract-check) are
    still returned so a human/orchestrator can read and judge them, but they do not block approval
    on their own. This mirrors `security_gate`'s zero-tolerance stance for the small set of
    patterns that have no legitimate reason to appear in code meant to run unattended on approval.

    When `risk_tier` classifies the contract `"high"` (it touches auth/payment/secrets or the
    `.ratchet/`/hook config surface), the agent-facing config scan also runs and its
    `flagged_lines` are added to the result -- purely additive, for a human read, never an
    automatic decision; the allow/deny logic above is unchanged. `project_root` defaults to the
    nearest ancestor of the contract with a `.ratchet/` or `.git/` marker (the contract's own
    parent when there is none).
    """
    findings = scan_contract_file_risk(contract_path)
    if any(f["severity"] == "high" for f in findings):
        result: dict = {"decision": "deny", "findings": findings}
    else:
        result = {"decision": "allow", "findings": findings}
    if risk_tier(contract_path) == "high":
        root = project_root if project_root is not None else _infer_project_root(contract_path)
        result["flagged_lines"] = scan_agent_facing_config(root)["flagged_lines"]
    return result


# --- Risk tiering and agent-facing config scanning (design spec section 3.5 / Task D) -----------
#
# `risk_tier` decides how much scanning a contract approval gets: a `low`-tier contract runs only
# the existing checks above; a `high`-tier one additionally surfaces lines in the project's own
# agent-facing config files (hooks, `.ratchet/config.json`, AGENTS.md/SKILL.md) that look like
# they grant capability or trust. Sourced from `old-coder`'s risk-scaled-effort principle (effort
# scales with risk: anything touching money/logins/data runs everything) and `ecc`'s AgentShield
# scope (the harness's own config is part of the attack surface). Both classifiers are simple
# word-boundary keyword heuristics, not formal analyzers: absence of a match is not proof of
# safety, and a flag exists to be read by a human, never to auto-deny.

_RISK_KEYWORDS = frozenset({
    "auth",
    "password",
    "payment",
    "secret",
    "token",
    "credential",
    "session",
    "login",
})
# Word boundaries so `secretary` or `tokenizer` never tier a contract high on their own, while
# compound names like `payment_webhook` still match on their keyword part.
_RISK_KEYWORD_RE = re.compile(r"(?i)\b(?:" + "|".join(_RISK_KEYWORDS) + r")\b")
# Hook/gate config files (e.g. `hooks.json`, `gate_check.py`, `.ratchet/config.json`) are
# themselves part of the attack surface, so a contract that names one is high-risk regardless of
# its prose.
_HOOK_GATE_REF_RE = re.compile(r"(?i)hook|gate")
# Words that mark a config line as *granting* capability or trust rather than merely mentioning a
# feature. Module-level like `_RISK_KEYWORDS` so the set is easy to extend.
_TRUST_GRANT_WORDS = ("trust", "allow", "bypass", "disable")
_TRUST_GRANT_RE = re.compile(r"(?i)\b(?:" + "|".join(_TRUST_GRANT_WORDS) + r")\b")


def risk_tier(contract_path: Path) -> str:
    """Classify a contract as `"high"` or `"low"` risk.

    `"high"` when the contract's path or its text content mentions any of `_RISK_KEYWORDS`
    (auth, password, payment, secret, token, credential, session, login), or when the path sits
    under `.ratchet/` or is itself a hook/gate config file. Everything else is `"low"`. A
    heuristic, not a security verdict: over-classification only means more scanning happens.
    """
    if _RISK_KEYWORD_RE.search(str(contract_path)):
        return "high"
    if any(part == ".ratchet" for part in contract_path.parts) or _HOOK_GATE_REF_RE.search(
        contract_path.name
    ):
        return "high"
    try:
        text = contract_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if _RISK_KEYWORD_RE.search(text) or _HOOK_GATE_REF_RE.search(text):
        return "high"
    return "low"


def _agent_facing_config_files(project_root: Path) -> list[Path]:
    """The project's own agent-facing config surface (ecc's AgentShield scope): `hooks/*.json`,
    `.ratchet/config.json`, and any `AGENTS.md`/`SKILL.md` anywhere in the tree.
    """
    files: list[Path] = []
    hooks_dir = project_root / "hooks"
    if hooks_dir.is_dir():
        files.extend(sorted(hooks_dir.glob("*.json")))
    ratchet_config = project_root / ".ratchet" / "config.json"
    if ratchet_config.is_file():
        files.append(ratchet_config)
    files.extend(sorted(project_root.rglob("AGENTS.md")))
    files.extend(sorted(project_root.rglob("SKILL.md")))
    return files


def scan_agent_facing_config(project_root: Path) -> dict:
    """Scan the project's own agent-facing config files for lines that look like they grant
    capability or trust.

    A line is flagged when it contains a trust-granting word (`trust`, `allow`, `bypass`,
    `disable`) -- the shape of config that lets an agent act without a human approving it. This
    is a simple heuristic, not a formal analyzer: it does not parse JSON or YAML, it can miss
    obfuscated grants and will over-flag legitimate uses of these words, and its output exists
    for a human read, never as an automatic decision.

    Returns `{"flagged_lines": [...]}`, each entry `{"path", "line", "text"}`, or
    `{"flagged_lines": []}` when clean.
    """
    flagged_lines: list[dict] = []
    for path in _agent_facing_config_files(project_root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if _TRUST_GRANT_RE.search(line):
                flagged_lines.append({"path": str(path), "line": line_no, "text": line.strip()})
    return {"flagged_lines": flagged_lines}


def _infer_project_root(contract_path: Path) -> Path:
    """Walk up from the contract to the directory whose `.ratchet/` or `.git/` marks it as the
    project root; fall back to the contract's own parent (a scratch contract, or a tmp dir in
    tests) when no marker exists.
    """
    start = contract_path.resolve().parent
    for directory in (start, *start.parents):
        if (directory / ".ratchet").is_dir() or (directory / ".git").is_dir():
            return directory
    return start


def main(argv: list[str]) -> int:
    usage = "usage: security.py scan-contract <contract.md> | scan-secrets <path> [path...]"
    if len(argv) < 2:
        print(json.dumps({"decision": "deny", "reason": usage}))
        return 2
    command, rest = argv[1], argv[2:]
    if command == "scan-contract" and len(rest) == 1:
        result = contract_approval_gate(Path(rest[0]))
    elif command == "scan-secrets" and rest:
        result = security_gate([Path(p) for p in rest])
    else:
        print(json.dumps({"decision": "deny", "reason": usage}))
        return 2
    return emit_decision(result)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
