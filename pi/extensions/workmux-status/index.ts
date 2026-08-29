import { spawn } from "node:child_process";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export type WorkmuxStatus = "working" | "done";
export type SetWorkmuxStatus = (status: WorkmuxStatus) => Promise<void>;

function runWorkmux(status: WorkmuxStatus): Promise<void> {
	if (!process.env.TMUX) return Promise.resolve();

	return new Promise((resolve) => {
		const child = spawn("workmux", ["set-window-status", status], {
			shell: false,
			stdio: "ignore",
		});
		child.on("error", () => resolve());
		child.on("close", () => resolve());
	});
}

export function registerWorkmuxStatus(pi: ExtensionAPI, setStatus: SetWorkmuxStatus = runWorkmux) {
	let pending = Promise.resolve();
	const update = (status: WorkmuxStatus) => {
		pending = pending.then(() => setStatus(status)).catch(() => undefined);
		return pending;
	};

	pi.on("input", () => update("working"));
	pi.on("agent_start", () => update("working"));
	pi.on("tool_execution_end", () => update("working"));
	pi.on("agent_settled", () => update("done"));
	pi.on("session_shutdown", () => update("done"));
}

export default function workmuxStatusExtension(pi: ExtensionAPI) {
	registerWorkmuxStatus(pi);
}
