import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const extensionDir = path.dirname(fs.realpathSync(fileURLToPath(import.meta.url)));
const rulesDir = path.resolve(extensionDir, "../../../assistants/communication-rules");
const scannerPath = path.join(rulesDir, "scanner.py");
const policyPath = path.join(rulesDir, "policy.json");
const rulesPath = path.join(rulesDir, "rules.md");

interface ScannerDecision {
	decision: "pass" | "block" | "yield" | "allow-revise" | "re-issue" | "remind";
	surface: "tierA" | "B1" | "B2";
	level: "warning" | "error";
	notice: string;
	inject_base_rules: boolean;
	append_correction: boolean;
	block_message: string;
	correction: string;
}

function runScanner(event: string, payload: Record<string, unknown>): Promise<ScannerDecision> {
	return new Promise((resolve, reject) => {
		const child = spawn(
			"python3",
			[scannerPath, "--policy-json", policyPath, "--rules", rulesPath, "pi", event],
			{ cwd: rulesDir, shell: false, stdio: ["pipe", "pipe", "pipe"] },
		);
		let stdout = "";
		let stderr = "";
		child.stdout.on("data", (data) => (stdout += data.toString()));
		child.stderr.on("data", (data) => (stderr += data.toString()));
		child.on("error", reject);
		child.on("close", (code) => {
			if (code !== 0) {
				reject(new Error(stderr.trim() || `communication scanner exited ${code}`));
				return;
			}
			try {
				resolve(JSON.parse(stdout) as ScannerDecision);
			} catch {
				reject(new Error(`communication scanner returned invalid JSON: ${stdout.trim()}`));
			}
		});
		child.stdin.end(JSON.stringify(payload));
	});
}

function assistantText(messages: readonly any[]): string {
	for (let index = messages.length - 1; index >= 0; index--) {
		const message = messages[index];
		if (message?.role !== "assistant" || !Array.isArray(message.content)) continue;
		return message.content
			.filter((part: any) => part?.type === "text" && typeof part.text === "string")
			.map((part: any) => part.text)
			.join("\n");
	}
	return "";
}

export default function communicationRulesExtension(pi: ExtensionAPI) {
	if (![scannerPath, policyPath, rulesPath].every(fs.existsSync)) {
		throw new Error(`Communication Rules files are missing under ${rulesDir}`);
	}

	const rulesText = fs.readFileSync(rulesPath, "utf8").trim();
	let blockedThisTurn = false;

	pi.on("turn_start", () => {
		blockedThisTurn = false;
	});

	pi.on("before_agent_start", async (_event, ctx) => {
		const decision = await runScanner("Context", {
			session_id: ctx.sessionManager.getSessionId(),
		});
		const additions: string[] = [];
		if (decision.inject_base_rules) {
			additions.push(
				`Reminder: Follow the Communication Rules for any prose you produce or write.\n\nCommunication Rules:\n${rulesText}`,
			);
		}
		if (decision.append_correction) additions.push(decision.correction);
		if (additions.length === 0) return;
		return {
			message: {
				customType: "communication-rules",
				content: additions.join("\n\n"),
				display: false,
			},
		};
	});

	pi.on("tool_call", async (event, ctx) => {
		let decision: ScannerDecision;
		try {
			decision = await runScanner("ToolCall", {
				session_id: ctx.sessionManager.getSessionId(),
				tool_name: event.toolName,
				tool_input: event.input,
				existing_blocked: blockedThisTurn,
			});
		} catch (error) {
			blockedThisTurn = true;
			return {
				block: true,
				reason: `Communication Rules scanner failed closed: ${error instanceof Error ? error.message : error}`,
			};
		}

		if (decision.decision === "block") {
			blockedThisTurn = true;
			return { block: true, reason: decision.block_message };
		}
		if ((decision.decision === "yield" || decision.decision === "allow-revise") && ctx.hasUI) {
			ctx.ui.notify(decision.notice, decision.level);
		}
	});

	pi.on("agent_end", async (event, ctx) => {
		const text = assistantText(event.messages);
		if (!text) return;
		try {
			const decision = await runScanner("AgentEnd", {
				session_id: ctx.sessionManager.getSessionId(),
				text,
				existing_blocked: blockedThisTurn,
			});
			if (decision.notice && ctx.hasUI) ctx.ui.notify(decision.notice, decision.level);
		} catch (error) {
			if (ctx.hasUI) {
				ctx.ui.notify(
					`Communication Rules final-response scan failed: ${error instanceof Error ? error.message : error}`,
					"error",
				);
			}
		}
	});
}
