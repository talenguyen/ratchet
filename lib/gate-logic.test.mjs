import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import {
  isRatchetToolingCall,
  isUnderRatchetStateBootstrapDir,
  resolveScriptsRoot,
  runGateCheck,
  handleToolCall,
} from "./gate-logic.mjs";

const REPO_ROOT = path.resolve(import.meta.dirname, "..");
const REAL_SCRIPTS_ROOT = path.join(REPO_ROOT, "scripts");

function makeScratchProject() {
  const cwd = mkdtempSync(path.join(tmpdir(), "ratchet-gate-test-"));
  mkdirSync(path.join(cwd, "ratchet-state", "contracts", "functional"), { recursive: true });
  return cwd;
}

function approveDemoContract(cwd) {
  const contractPath = path.join(cwd, "ratchet-state", "contracts", "functional", "demo.md");
  writeFileSync(contractPath, "# demo\n");
  execFileSync("python3", [
    "-c",
    `import sys; sys.path.insert(0, ${JSON.stringify(REAL_SCRIPTS_ROOT)}); ` +
      `from pathlib import Path; from gate_check import approve_contract; ` +
      `approve_contract(Path(${JSON.stringify(contractPath)}))`,
  ]);
  return contractPath;
}

test("isRatchetToolingCall recognizes ratchet script invocations, not arbitrary commands", () => {
  assert.equal(isRatchetToolingCall('python3 "$RATCHET_SCRIPTS_ROOT/gate_check.py" a b'), true);
  assert.equal(
    isRatchetToolingCall(
      'PYTHONPATH="$RATCHET_SCRIPTS_ROOT" python3 -c "from scripts.contracts import run_checks"',
    ),
    true,
  );
  assert.equal(isRatchetToolingCall("from gate_check import approve_contract"), true);
  assert.equal(isRatchetToolingCall("npm test"), false);
  assert.equal(isRatchetToolingCall("echo hi > foo.py"), false);
});

test("isUnderRatchetStateBootstrapDir allows contract/change scaffolding paths only", () => {
  const cwd = "/proj";
  assert.equal(isUnderRatchetStateBootstrapDir("ratchet-state/contracts/functional/foo.md", cwd), true);
  assert.equal(isUnderRatchetStateBootstrapDir("ratchet-state/changes/foo/proposal.md", cwd), true);
  assert.equal(isUnderRatchetStateBootstrapDir("src/foo.py", cwd), false);
  assert.equal(isUnderRatchetStateBootstrapDir("ratchet-state/RUNG_STATS.json", cwd), false);
});

test("resolveScriptsRoot resolves relative to the extension's own file, not cwd", () => {
  const fakeUrl = "file:///repo/extensions/ratchet-gate.ts";
  assert.equal(resolveScriptsRoot(fakeUrl), path.join("/repo", "scripts"));
});

test("runGateCheck denies with no approved contract, allows once one is approved", () => {
  const cwd = makeScratchProject();
  writeFileSync(path.join(cwd, "ratchet-state", "contracts", "functional", "demo.md"), "# demo\n");

  const denied = runGateCheck(REAL_SCRIPTS_ROOT, cwd);
  assert.equal(denied.decision, "deny");

  approveDemoContract(cwd);

  const allowed = runGateCheck(REAL_SCRIPTS_ROOT, cwd);
  assert.equal(allowed.decision, "allow");
});

test("handleToolCall blocks a bash write attempt with no approved contract", async () => {
  const cwd = makeScratchProject();
  const event = { toolName: "bash", input: { command: "echo hi > src/foo.py" } };
  const ctx = { cwd };
  const result = await handleToolCall(event, ctx, REAL_SCRIPTS_ROOT);
  assert.equal(result?.block, true);
  assert.match(event.input.command, /^export RATCHET_SCRIPTS_ROOT="/);
});

test("handleToolCall allows writing the contract file itself before any approval exists", async () => {
  const cwd = makeScratchProject();
  const event = { toolName: "write", input: { path: "ratchet-state/contracts/functional/demo.md" } };
  const ctx = { cwd };
  const result = await handleToolCall(event, ctx, REAL_SCRIPTS_ROOT);
  assert.equal(result, undefined);
});

test("handleToolCall allows a bash call that only invokes ratchet's own scripts", async () => {
  const cwd = makeScratchProject();
  const event = {
    toolName: "bash",
    input: { command: 'python3 "$RATCHET_SCRIPTS_ROOT/gate_check.py" ratchet-state/contracts' },
  };
  const ctx = { cwd };
  const result = await handleToolCall(event, ctx, REAL_SCRIPTS_ROOT);
  assert.equal(result, undefined);
});

test("handleToolCall allows a write once a contract is approved", async () => {
  const cwd = makeScratchProject();
  approveDemoContract(cwd);
  const event = { toolName: "write", input: { path: "src/foo.py" } };
  const ctx = { cwd };
  const result = await handleToolCall(event, ctx, REAL_SCRIPTS_ROOT);
  assert.equal(result, undefined);
});
