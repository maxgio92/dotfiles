import assert from "node:assert/strict";
import test from "node:test";
import {
	CODE_REVIEW_COMMAND,
	IMPLEMENT_REVIEW_COMMANDS,
	isConverged,
	parseStructuredReview,
	parseWorkflowArgs,
} from "./logic.ts";

test("defines the code workflow commands", () => {
	assert.deepEqual(IMPLEMENT_REVIEW_COMMANDS, ["implement-review", "code-implement"]);
	assert.equal(CODE_REVIEW_COMMAND, "code-review");
});

test("parseWorkflowArgs uses the default round count", () => {
	assert.deepEqual(parseWorkflowArgs("add focused tests"), {
		task: "add focused tests",
		maxRounds: 3,
	});
});

test("parseWorkflowArgs accepts both max-rounds forms", () => {
	assert.deepEqual(parseWorkflowArgs("--max-rounds 2 add tests"), {
		task: "add tests",
		maxRounds: 2,
	});
	assert.deepEqual(parseWorkflowArgs("add tests --max-rounds=4"), {
		task: "add tests",
		maxRounds: 4,
	});
});

test("parseWorkflowArgs rejects missing tasks and invalid limits", () => {
	assert.throws(() => parseWorkflowArgs(""), /Usage:/);
	assert.throws(() => parseWorkflowArgs("--max-rounds task"), /integer/);
	assert.throws(() => parseWorkflowArgs("--max-rounds=11 task"), /1 to 10/);
});

test("isConverged stops only when blocking findings are absent", () => {
	assert.equal(isConverged({ findings: [] }), true);
	assert.equal(
		isConverged({
			findings: [{ title: "rename", severity: "non-blocking", detail: "Match the package vocabulary." }],
		}),
		true,
	);
	assert.equal(
		isConverged({
			findings: [{ title: "lost error", severity: "blocking", detail: "The caller cannot observe failure." }],
		}),
		false,
	);
});

test("parseStructuredReview accepts only the Claude workflow contract", () => {
	const review = {
		findings: [
			{
				title: "lost error",
				severity: "blocking",
				file: "foo.go",
				detail: "The caller cannot observe failure.",
			},
		],
	};
	assert.deepEqual(parseStructuredReview(review), review);
	assert.equal(parseStructuredReview({ ...review, verdict: "request-changes" }), undefined);
	assert.equal(parseStructuredReview({ findings: [{ ...review.findings[0], confidence: 1 }] }), undefined);
	assert.equal(parseStructuredReview({ findings: [{ ...review.findings[0], severity: "block" }] }), undefined);
});
