import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import * as path from "node:path";
import test from "node:test";
import communicationRulesExtension from "./index.ts";

test("Pi handlers block tool prose and reissue a final-response correction", async () => {
	const stateDir = mkdtempSync(path.join(tmpdir(), "pi-communication-rules-test-"));
	process.env.TRIPWIRE_STRIKE_DIR = path.join(stateDir, "strikes");
	process.env.TRIPWIRE_REISSUE_DIR = path.join(stateDir, "reissue");
	process.env.TRIPWIRE_INJECTED_DIR = path.join(stateDir, "injected");

	const handlers = new Map<string, (...args: any[]) => any>();
	const notifications: string[] = [];
	communicationRulesExtension({
		on(event: string, handler: (...args: any[]) => any) {
			handlers.set(event, handler);
		},
	} as any);

	const sessionId = `pi-test-${Date.now()}`;
	const context = {
		sessionManager: { getSessionId: () => sessionId },
		hasUI: true,
		ui: { notify: (message: string) => notifications.push(message) },
	};

	const firstContext = await handlers.get("before_agent_start")?.({}, context);
	assert.match(firstContext.message.content, /Communication Rules/);

	await handlers.get("turn_start")?.({}, context);
	const blocked = await handlers.get("tool_call")?.(
		{
			toolName: "write",
			input: { path: "note.md", content: "A seamless note." },
		},
		context,
	);
	assert.equal(blocked.block, true);
	assert.match(blocked.reason, /Blocked\. Revise this prose/);

	await handlers.get("turn_start")?.({}, context);
	await handlers.get("agent_end")?.(
		{
			messages: [{ role: "assistant", content: [{ type: "text", text: "A seamless answer." }] }],
		},
		context,
	);
	assert.ok(notifications.some((message) => message.includes("correcting next reply")));

	const correctedContext = await handlers.get("before_agent_start")?.({}, context);
	assert.match(correctedContext.message.content, /previous reply broke the Communication Rules/);
});
