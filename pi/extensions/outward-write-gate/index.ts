/**
 * Outward Write Gate Extension
 *
 * Prompts for confirmation before bash commands that publish work:
 * git push, gh pr create/comment/review/merge/close, gh issue
 * create/comment. Blocks them outright when no UI is available.
 *
 * Counterpart of the `ask` permission list in Claude Code settings and
 * the codex workspace-write sandbox: the upstream-contribution skill
 * states the policy; this enforces it in pi.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	// \bgit\b[^\n;|&]* tolerates flags between git and the subcommand
	// (e.g. `git -C repo push`), while ; | & end the match so a later
	// command in a compound line cannot smuggle the subcommand past it.
	const outwardPatterns = [
		/\bgit\b[^\n;|&]*\bpush\b/,
		/\bgh\s+pr\s+(create|comment|review|merge|close)\b/,
		/\bgh\s+issue\s+(create|comment)\b/,
		/\bgh\s+api\b[^\n;|&]*(-X|--method)\s+(POST|PUT|PATCH|DELETE)\b/i,
	];

	pi.on("tool_call", async (event, ctx) => {
		if (event.toolName !== "bash") return undefined;

		const command = event.input.command as string;
		if (!outwardPatterns.some((pattern) => pattern.test(command))) return undefined;

		if (!ctx.hasUI) {
			return {
				block: true,
				reason: "Outward write blocked: no UI to ask for approval. Stage the artifact and report it instead.",
			};
		}

		const choice = await ctx.ui.select(`Outward write:\n\n  ${command}\n\nAllow?`, ["Yes", "No"]);
		if (choice !== "Yes") {
			return { block: true, reason: "Outward write declined by user" };
		}
		return undefined;
	});
}
