import assert from "node:assert/strict";
import test from "node:test";
import { formatDuration, parseDuration, parseLoopRequest } from "./logic.ts";

test("parseDuration accepts custom and compound intervals", () => {
	assert.equal(parseDuration("45s"), 45_000);
	assert.equal(parseDuration("2m30s"), 150_000);
	assert.equal(parseDuration("1h15m"), 4_500_000);
	assert.equal(parseDuration("1d2h3m4s"), 93_784_000);
});

test("parseDuration rejects invalid intervals", () => {
	assert.equal(parseDuration(""), undefined);
	assert.equal(parseDuration("0s"), undefined);
	assert.equal(parseDuration("1.5m"), undefined);
	assert.equal(parseDuration("5x"), undefined);
	assert.equal(parseDuration("1m later"), undefined);
});

test("parseLoopRequest supports explicit and default intervals", () => {
	assert.deepEqual(parseLoopRequest("2m30s check CI"), {
		intervalMs: 150_000,
		prompt: "check CI",
	});
	assert.deepEqual(parseLoopRequest("check CI"), {
		intervalMs: 600_000,
		prompt: "check CI",
	});
	assert.match(parseLoopRequest("45s").prompt, /Continue unfinished work/);
	assert.match(parseLoopRequest("").prompt, /Continue unfinished work/);
});

test("parseLoopRequest rejects malformed interval arguments", () => {
	assert.throws(() => parseLoopRequest("1.5m check CI"), /Invalid loop interval/);
	assert.throws(() => parseLoopRequest("0s check CI"), /Invalid loop interval/);
});

test("formatDuration produces reusable interval strings", () => {
	assert.equal(formatDuration(45_000), "45s");
	assert.equal(formatDuration(150_000), "2m30s");
	assert.equal(formatDuration(93_784_000), "1d2h3m4s");
});
