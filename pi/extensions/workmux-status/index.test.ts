import assert from "node:assert/strict";
import test from "node:test";
import { registerWorkmuxStatus, type WorkmuxStatus } from "./index.ts";

test("maps Pi lifecycle events to ordered Workmux states", async () => {
	const handlers = new Map<string, (...args: any[]) => any>();
	const statuses: WorkmuxStatus[] = [];
	registerWorkmuxStatus(
		{
			on(event: string, handler: (...args: any[]) => any) {
				handlers.set(event, handler);
			},
		} as any,
		async (status) => {
			statuses.push(status);
		},
	);

	await handlers.get("input")?.({}, {});
	await handlers.get("agent_start")?.({}, {});
	await handlers.get("tool_execution_end")?.({}, {});
	await handlers.get("agent_settled")?.({}, {});
	await handlers.get("session_shutdown")?.({}, {});

	assert.deepEqual(statuses, ["working", "working", "working", "done", "done"]);
});

test("status command failures do not break Pi events", async () => {
	const handlers = new Map<string, (...args: any[]) => any>();
	registerWorkmuxStatus(
		{
			on(event: string, handler: (...args: any[]) => any) {
				handlers.set(event, handler);
			},
		} as any,
		async () => {
			throw new Error("workmux unavailable");
		},
	);

	await assert.doesNotReject(() => handlers.get("agent_start")?.({}, {}));
	await assert.doesNotReject(() => handlers.get("agent_settled")?.({}, {}));
});
