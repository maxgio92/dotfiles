import assert from "node:assert/strict";
import test from "node:test";
import { registerLoopCommands, type LoopClock } from "./index.ts";

test("loop commands run serially and stop cleanly", async () => {
	const commands = new Map<string, any>();
	const handlers = new Map<string, (...args: any[]) => any>();
	const messages: string[] = [];
	const notifications: string[] = [];
	const timers = new Map<number, () => void>();
	let nextTimer = 1;

	const clock: LoopClock = {
		set(callback) {
			const id = nextTimer++;
			timers.set(id, callback);
			return id as unknown as ReturnType<typeof setTimeout>;
		},
		clear(timer) {
			timers.delete(timer as unknown as number);
		},
	};
	const pi = {
		registerCommand(name: string, command: any) {
			commands.set(name, command);
		},
		on(event: string, handler: (...args: any[]) => any) {
			handlers.set(event, handler);
		},
		sendUserMessage(message: string) {
			messages.push(message);
		},
	};
	const context = { ui: { notify: (message: string) => notifications.push(message) } };

	registerLoopCommands(pi as any, clock);
	await commands.get("loop").handler("2m30s check CI", context);
	assert.match(notifications.at(-1), /2m30s/);
	assert.equal(timers.size, 1);

	const firstTimer = timers.values().next().value;
	assert.ok(firstTimer);
	timers.clear();
	firstTimer();
	assert.deepEqual(messages, ["check CI"]);
	assert.equal(timers.size, 0);

	await handlers.get("agent_settled")?.({}, context);
	assert.equal(timers.size, 1);
	await commands.get("loop-stop").handler("1", context);
	assert.equal(timers.size, 0);
	assert.match(notifications.at(-1), /Stopped loop 1/);
});
