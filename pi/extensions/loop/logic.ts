const DEFAULT_INTERVAL_MS = 10 * 60 * 1000;
const DEFAULT_PROMPT = [
	"Continue unfinished work from this session.",
	"Then check the current branch for pending review comments, failed checks, or merge conflicts.",
	"If nothing needs action, report that in one line.",
].join(" ");

const UNIT_MS: Record<string, number> = {
	d: 24 * 60 * 60 * 1000,
	h: 60 * 60 * 1000,
	m: 60 * 1000,
	s: 1000,
};

export interface LoopRequest {
	intervalMs: number;
	prompt: string;
}

export function parseDuration(value: string): number | undefined {
	if (!value) return undefined;
	let total = 0;
	let offset = 0;
	const pattern = /(\d+)(d|h|m|s)/gi;

	for (const match of value.matchAll(pattern)) {
		if (match.index !== offset) return undefined;
		total += Number.parseInt(match[1], 10) * UNIT_MS[match[2].toLowerCase()];
		offset = match.index + match[0].length;
	}

	if (offset !== value.length || total === 0) return undefined;
	return total;
}

export function parseLoopRequest(args: string): LoopRequest {
	const input = args.trim();
	if (!input) return { intervalMs: DEFAULT_INTERVAL_MS, prompt: DEFAULT_PROMPT };

	const [first, ...rest] = input.split(/\s+/);
	const intervalMs = parseDuration(first);
	if (intervalMs === undefined) {
		if (/^\d/.test(first)) throw new Error(`Invalid loop interval: ${first}`);
		return { intervalMs: DEFAULT_INTERVAL_MS, prompt: input };
	}

	const prompt = rest.join(" ").trim();
	return { intervalMs, prompt: prompt || DEFAULT_PROMPT };
}

export function formatDuration(milliseconds: number): string {
	let seconds = Math.floor(milliseconds / 1000);
	const parts: string[] = [];
	for (const [unit, size] of [
		["d", 86400],
		["h", 3600],
		["m", 60],
		["s", 1],
	] as const) {
		const count = Math.floor(seconds / size);
		if (count > 0) parts.push(`${count}${unit}`);
		seconds %= size;
	}
	return parts.join("") || "0s";
}
