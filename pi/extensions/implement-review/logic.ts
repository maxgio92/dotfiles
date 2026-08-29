const DEFAULT_MAX_ROUNDS = 3;
const MAX_ALLOWED_ROUNDS = 10;

export const IMPLEMENT_REVIEW_COMMANDS = ["implement-review", "code-implement"] as const;
export const CODE_REVIEW_COMMAND = "code-review";

export interface ReviewFinding {
	title: string;
	severity: "blocking" | "non-blocking";
	file?: string;
	detail: string;
}

export interface StructuredReview {
	findings: ReviewFinding[];
}

export function parseWorkflowArgs(input: string): { task: string; maxRounds: number } {
	const tokens = input.trim().split(/\s+/).filter(Boolean);
	let maxRounds = DEFAULT_MAX_ROUNDS;
	const taskTokens: string[] = [];

	for (let i = 0; i < tokens.length; i++) {
		const token = tokens[i];
		if (token === "--max-rounds") {
			const value = tokens[++i];
			if (!value) throw new Error("--max-rounds requires a value");
			maxRounds = parseRoundCount(value);
			continue;
		}
		if (token.startsWith("--max-rounds=")) {
			maxRounds = parseRoundCount(token.slice("--max-rounds=".length));
			continue;
		}
		taskTokens.push(token);
	}

	const task = taskTokens.join(" ").trim();
	if (!task) throw new Error("Usage: /implement-review [--max-rounds N] <coding task>");
	return { task, maxRounds };
}

function parseRoundCount(value: string): number {
	const parsed = Number(value);
	if (!Number.isInteger(parsed) || parsed < 1 || parsed > MAX_ALLOWED_ROUNDS) {
		throw new Error(`--max-rounds must be an integer from 1 to ${MAX_ALLOWED_ROUNDS}`);
	}
	return parsed;
}

export function isConverged(review: StructuredReview): boolean {
	return review.findings.every((finding) => finding.severity !== "blocking");
}

export function parseStructuredReview(value: unknown): StructuredReview | undefined {
	if (!isRecord(value) || Object.keys(value).some((key) => key !== "findings") || !Array.isArray(value.findings)) {
		return undefined;
	}
	const findings: ReviewFinding[] = [];
	for (const finding of value.findings) {
		if (
			!isRecord(finding) ||
			Object.keys(finding).some((key) => !["title", "severity", "file", "detail"].includes(key)) ||
			typeof finding.title !== "string" ||
			(finding.severity !== "blocking" && finding.severity !== "non-blocking") ||
			typeof finding.detail !== "string" ||
			(finding.file !== undefined && typeof finding.file !== "string")
		) {
			return undefined;
		}
		findings.push({
			title: finding.title,
			severity: finding.severity,
			...(finding.file === undefined ? {} : { file: finding.file }),
			detail: finding.detail,
		});
	}
	return { findings };
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}
