import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const RATCHET_SCRIPT_NAMES = [
  "gate_check",
  "security",
  "contracts",
  "rung_stats",
  "changes",
  "audit",
  "memory",
  "providers",
  "quality",
  "consistency",
  "loop_state",
  "cli_support",
];

const NAMES = RATCHET_SCRIPT_NAMES.join("|");
const RATCHET_TOOLING_PATTERN = new RegExp(
  `\\b(?:${NAMES})\\.py\\b|\\bfrom\\s+(?:scripts\\.)?(?:${NAMES})\\s+import\\b`,
);

/** True if `command` invokes one of Ratchet's own scripts -- the scanning/approval machinery
 * that must run before a contract exists, so it can never itself be gated on one existing.
 * Matches both invocation shapes: CLI entry points (`<name>.py`) and library calls
 * (`from <name> import ...` / `from scripts.<name> import ...`). */
export function isRatchetToolingCall(command) {
  return RATCHET_TOOLING_PATTERN.test(command);
}

/** True if `targetPath` (resolved against `cwd`) is under ratchet-state/contracts or
 * ratchet-state/changes -- drafting or scaffolding a contract can never depend on a contract
 * already being approved, so writes/edits here are always allowed regardless of gate state. */
export function isUnderRatchetStateBootstrapDir(targetPath, cwd) {
  const resolved = path.resolve(cwd, targetPath);
  for (const sub of ["contracts", "changes"]) {
    const dir = path.resolve(cwd, "ratchet-state", sub);
    if (resolved === dir || resolved.startsWith(dir + path.sep)) return true;
  }
  return false;
}

/** Resolve the shared, single-source-of-truth scripts directory relative to this extension's own
 * installed file location -- correct regardless of whether pi installed globally, project-locally,
 * or from a local dev clone. */
export function resolveScriptsRoot(extensionFileUrl) {
  const extensionDir = path.dirname(fileURLToPath(extensionFileUrl));
  return path.join(extensionDir, "..", "scripts");
}

/** Shell out to the existing, unmodified gate_check.py -- the one place the gate's decision logic
 * lives. Never reimplemented here. */
export function runGateCheck(scriptsRoot, cwd) {
  const contractsDir = path.join(cwd, "ratchet-state", "contracts");
  const changesDir = path.join(cwd, "ratchet-state", "changes");
  const gateCheckPath = path.join(scriptsRoot, "gate_check.py");
  let stdout;
  try {
    stdout = execFileSync("python3", [gateCheckPath, contractsDir, changesDir], {
      encoding: "utf-8",
    });
  } catch (error) {
    stdout = error.stdout;
  }
  return JSON.parse(stdout);
}

/** The full gate decision for one tool call. Returns `{ block: true, reason }` to deny, or
 * `undefined` to allow. Mutates `event.input.command` in place for bash calls so every bash
 * invocation -- gated or not -- has $RATCHET_SCRIPTS_ROOT available. */
export async function handleToolCall(event, ctx, scriptsRoot) {
  if (event.toolName === "bash") {
    const originalCommand = event.input.command;
    event.input.command = `export RATCHET_SCRIPTS_ROOT="${scriptsRoot}"\n${originalCommand}`;
    if (isRatchetToolingCall(originalCommand)) {
      return;
    }
  } else if (
    (event.toolName === "write" || event.toolName === "edit") &&
    isUnderRatchetStateBootstrapDir(event.input.path, ctx.cwd)
  ) {
    return;
  }

  const result = runGateCheck(scriptsRoot, ctx.cwd);
  if (result.decision !== "allow") {
    return { block: true, reason: `Ratchet capability gate denied this action: ${result.reason}` };
  }
}
