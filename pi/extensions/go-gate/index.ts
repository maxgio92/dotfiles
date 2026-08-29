import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const extensionDir = path.dirname(fs.realpathSync(fileURLToPath(import.meta.url)));
const gatePath = path.resolve(extensionDir, "../../../assistants/go-gate/go-gate.sh");

export interface GateResult {
	ok: boolean;
	message: string;
}

export type RunGate = (
	mode: "file" | "final",
	payload: Record<string, unknown>,
	cwd: string,
) => Promise<GateResult>;

function runGate(mode: "file" | "final", payload: Record<string, unknown>, cwd: string): Promise<GateResult> {
	return new Promise((resolve) => {
		const child = spawn("bash", [gatePath, mode], {
			cwd,
			env: { ...process.env, CLAUDE_PROJECT_DIR: cwd },
			shell: false,
			stdio: ["pipe", "pipe", "pipe"],
		});
		let stderr = "";
		child.stderr.on("data", (data) => (stderr += data.toString()));
		child.on("error", (error) => resolve({ ok: false, message: `go-gate failed to run: ${error.message}` }));
		child.on("close", (code) => resolve({ ok: code === 0, message: stderr.trim() }));
		child.stdin.end(JSON.stringify(payload));
	});
}

function editedPath(event: { toolName: string; input: Record<string, unknown> }): string {
	if (event.toolName !== "edit" && event.toolName !== "write") return "";
	const value = event.input.path ?? event.input.file_path;
	return typeof value === "string" ? value : "";
}

export function registerGoGate(pi: ExtensionAPI, check: RunGate = runGate) {
	let finalCorrectionSent = false;

	pi.on("input", (event) => {
		if (event.source !== "extension") finalCorrectionSent = false;
	});

	pi.on("tool_result", async (event, ctx) => {
		if (event.isError) return;
		const filePath = editedPath(event);
		if (!filePath.endsWith(".go")) return;

		const result = await check("file", { tool_input: { file_path: filePath } }, ctx.cwd);
		if (result.ok) return;
		return {
			content: [...event.content, { type: "text" as const, text: result.message }],
			isError: true,
		};
	});

	pi.on("agent_settled", async (_event, ctx) => {
		const result = await check("final", {}, ctx.cwd);
		if (result.ok) return;
		if (!finalCorrectionSent) {
			finalCorrectionSent = true;
			pi.sendUserMessage(result.message);
			return;
		}
		if (ctx.hasUI) ctx.ui.notify(result.message, "error");
	});
}

export default function goGateExtension(pi: ExtensionAPI) {
	if (!fs.existsSync(gatePath)) throw new Error(`Go gate is missing at ${gatePath}`);
	registerGoGate(pi);
}
