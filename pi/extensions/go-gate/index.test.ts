import assert from "node:assert/strict";
import test from "node:test";
import { registerGoGate, type GateResult } from "./index.ts";

function harness(results: GateResult[]) {
	const handlers = new Map<string, (...args: any[]) => any>();
	const messages: string[] = [];
	const notices: string[] = [];
	const calls: string[] = [];
	registerGoGate(
		{
			on(event: string, handler: (...args: any[]) => any) {
				handlers.set(event, handler);
			},
			sendUserMessage(message: string) {
				messages.push(message);
			},
		} as any,
		async (mode) => {
			calls.push(mode);
			return results.shift() ?? { ok: true, message: "" };
		},
	);
	return {
		handlers,
		messages,
		notices,
		calls,
		context: { cwd: "/repo", hasUI: true, ui: { notify: (message: string) => notices.push(message) } },
	};
}

test("marks an unformatted Go edit as a tool error", async () => {
	const testRun = harness([{ ok: false, message: "run gofmt" }]);
	const result = await testRun.handlers.get("tool_result")?.(
		{
			toolName: "edit",
			input: { path: "/repo/main.go" },
			content: [{ type: "text", text: "edited" }],
			isError: false,
		},
		testRun.context,
	);

	assert.equal(result.isError, true);
	assert.equal(result.content.at(-1).text, "run gofmt");
	assert.deepEqual(testRun.calls, ["file"]);
});

test("sends one correction when the final gate keeps failing", async () => {
	const failure = { ok: false, message: "go test failed" };
	const testRun = harness([failure, failure]);

	await testRun.handlers.get("agent_settled")?.({}, testRun.context);
	await testRun.handlers.get("agent_settled")?.({}, testRun.context);

	assert.deepEqual(testRun.messages, ["go test failed"]);
	assert.deepEqual(testRun.notices, ["go test failed"]);
	assert.deepEqual(testRun.calls, ["final", "final"]);
});
