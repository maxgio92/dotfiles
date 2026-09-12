/**
 * Outward Write Gate Extension
 *
 * Prompts for confirmation before bash commands that publish work:
 * git push; gh pr create/comment/review/merge/close/reopen/edit/ready/lock/unlock;
 * gh issue create/comment/edit/close/reopen/delete/transfer/pin/lock/unlock;
 * gh release; gh repo edit; gh workflow run; gh secret and gh variable
 * set/delete/remove; gh api with a mutating method or any request field;
 * gh-review-reply (the review-thread reply helper in bin/).
 * Blocks them outright when no UI is available.
 *
 * Counterpart of the `ask` permission list in Claude Code settings and
 * the codex workspace-write sandbox: the upstream-contribution skill
 * states the policy; this enforces it in pi.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// \bgit\b[^\n;|&]* tolerates flags between git and the subcommand
// (e.g. `git -C repo push`), while ; | & end the match so a later
// command in a compound line cannot smuggle the subcommand past it.
export const outwardPatterns: readonly RegExp[] = [
	/\bgit\b[^\n;|&]*\bpush\b/,
	/\bgh\s+pr\s+(create|comment|review|merge|close|reopen|edit|ready|lock|unlock)\b/,
	/\bgh\s+issue\s+(create|comment|edit|close|reopen|delete|transfer|pin|lock|unlock)\b/,
	/\bgh\s+(secret|variable)\s+(set|delete|remove)\b/,
	/\bgh\s+release\b/,
	/\bgh\s+repo\s+edit\b/,
	/\bgh\s+workflow\s+run\b/,
	// pflag accepts attached (-XPOST) and equals (--method=POST) forms.
	// The method value may be quoted (--method "POST", -X 'DELETE').
	// The argument run skips over quoted strings whole, so a pipe or
	// semicolon inside a quoted value (-H 'Accept: a|b') does not end the
	// command early and hide a later flag. A backslash-escaped quote
	// (-H "X: a\"b") is not a closing delimiter. The flag itself may be
	// quoted ('-X', "--method"), so optional quotes surround it.
	/\bgh\s+api\b(?:[^\n;|&'"\\]|\\.|'[^'\n]*'|"(?:[^"\\\n]|\\.)*")*["']?(-X|--method)["']?[\s=]*["']?(POST|PUT|PATCH|DELETE)\b/i,
	// gh api switches to POST as soon as a request field is given, so a
	// field flag is a write even without an explicit method. Short flags
	// may carry the value attached (-fbody=hi) or be quoted ('-f').
	/\bgh\s+api\b(?:[^\n;|&'"\\]|\\.|'[^'\n]*'|"(?:[^"\\\n]|\\.)*")*\s["']?(-[fF]|--field|--raw-field|--input)["']?([\s=]|\S)/,
	/\bgh-review-reply\b/,
];

export function isOutwardWrite(command: string): boolean {
	// A backslash-newline continues the same shell command, so join it
	// before matching; the patterns stop at a bare newline on purpose.
	const joined = command.replace(/\\\n/g, "");
	return outwardPatterns.some((pattern) => pattern.test(joined));
}

export default function (pi: ExtensionAPI) {
	pi.on("tool_call", async (event, ctx) => {
		if (event.toolName !== "bash") return undefined;

		const command = event.input.command as string;
		if (!isOutwardWrite(command)) return undefined;

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
