import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { handleToolCall, resolveScriptsRoot } from "../lib/gate-logic.mjs";

export default function (pi: ExtensionAPI) {
  const scriptsRoot = resolveScriptsRoot(import.meta.url);
  pi.on("tool_call", async (event, ctx) => handleToolCall(event, ctx, scriptsRoot));
}
