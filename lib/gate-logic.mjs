import path from "node:path";
import { fileURLToPath } from "node:url";

export function isUnderProjectRoot(targetPath, cwd) {
  const root = path.resolve(cwd);
  const resolved = path.resolve(cwd, targetPath);
  return resolved === root || resolved.startsWith(root + path.sep);
}

export function isUnderDotRatchet(targetPath, cwd) {
  const dir = path.resolve(cwd, ".ratchet");
  const resolved = path.resolve(cwd, targetPath);
  return resolved === dir || resolved.startsWith(dir + path.sep);
}

export function isUnderContractsDir(targetPath, cwd) {
  const dir = path.resolve(cwd, "tests", "contracts");
  const resolved = path.resolve(cwd, targetPath);
  return resolved === dir || resolved.startsWith(dir + path.sep);
}

/** Deny-direction check. Deliberately a substring match: over-triggering here only ever produces
 * an incorrect denial (safe), never an incorrect allow. */
export function touchesRatchetApprovedDir(command) {
  return command.includes(".ratchet/approved") || command.includes(".ratchet\\approved");
}

const RATCHET_CORE_INVOKE =
  '(?:python3|python)\\s+"?\\$?RATCHET_SCRIPTS_ROOT"?/?ratchet_core\\.py"?';

/** Allow-direction check. Anchored ^...$ so nothing can be prepended or appended -- this is the
 * fix for the substring bug that let a comment referencing any script name exempt anything. */
const APPROVE_RE = new RegExp(`^${RATCHET_CORE_INVOKE}\\s+approve\\s+(\\S+)\\s*$`);

export function matchApproveInvocation(command) {
  const match = command.trim().match(APPROVE_RE);
  return match ? match[1] : null;
}

const EXACT_TOOLING_RE = new RegExp(`^${RATCHET_CORE_INVOKE}\\s+(status|verify)\\s+\\S+\\s*$`);

export function isExactRatchetToolingCall(command) {
  return EXACT_TOOLING_RE.test(command.trim());
}

export function resolveScriptsRoot(extensionFileUrl) {
  const extensionDir = path.dirname(fileURLToPath(extensionFileUrl));
  return path.join(extensionDir, "..", "scripts");
}

export async function handleToolCall(event, ctx, scriptsRoot) {
  if (event.toolName === "bash") {
    const originalCommand = event.input.command;
    event.input.command = `export RATCHET_SCRIPTS_ROOT="${scriptsRoot}"\n${originalCommand}`;
    const trimmed = originalCommand.trim();

    if (touchesRatchetApprovedDir(trimmed)) {
      return { block: true, reason: "writes to .ratchet/approved/ must go through the approve flow" };
    }
    if (matchApproveInvocation(trimmed) !== null) {
      const confirmed = await ctx.ui.confirm(
        "Approve Ratchet contract?",
        "This records your approval for a contract. Continue only if you have read it.",
      );
      if (!confirmed) {
        return { block: true, reason: "approval declined by the human" };
      }
      return; // human confirmed -- let the approve command actually run
    }
    if (isExactRatchetToolingCall(trimmed)) {
      return; // read-only ratchet tooling, always allowed
    }
    return; // any other bash command: not gated by this design (spec §10, stated limitation)
  }

  if (event.toolName !== "write" && event.toolName !== "edit") {
    return; // every other tool (read/grep/ls/glob/etc.) is never gated
  }

  const targetPath = event.input.path;

  if (isUnderContractsDir(targetPath, ctx.cwd)) {
    return; // bootstrap: drafting a contract test file never depends on one being approved
  }
  if (isUnderDotRatchet(targetPath, ctx.cwd)) {
    return { block: true, reason: "writes to .ratchet/ must go through the approve flow, not write/edit" };
  }
  if (!isUnderProjectRoot(targetPath, ctx.cwd)) {
    return { block: true, reason: "writes outside the project root are never allowed by this gate" };
  }

  return; // within the project root, outside .ratchet -- allowed (see plan's scope-adjustment note)
}
