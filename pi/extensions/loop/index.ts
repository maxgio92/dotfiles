import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { formatDuration, parseLoopRequest } from "./logic.ts";

interface ActiveLoop {
	id: number;
	intervalMs: number;
	prompt: string;
	timer?: ReturnType<typeof setTimeout>;
	waitingForSettle: boolean;
}

export interface LoopClock {
	set(callback: () => void, delay: number): ReturnType<typeof setTimeout>;
	clear(timer: ReturnType<typeof setTimeout>): void;
}

const systemClock: LoopClock = {
	set: (callback, delay) => setTimeout(callback, delay),
	clear: (timer) => clearTimeout(timer),
};

export function registerLoopCommands(pi: ExtensionAPI, clock: LoopClock = systemClock) {
	const loops = new Map<number, ActiveLoop>();
	let nextId = 1;

	const clearLoop = (loop: ActiveLoop) => {
		if (loop.timer) clock.clear(loop.timer);
		loop.timer = undefined;
		loops.delete(loop.id);
	};

	const schedule = (loop: ActiveLoop) => {
		if (!loops.has(loop.id)) return;
		loop.waitingForSettle = false;
		loop.timer = clock.set(() => {
			loop.timer = undefined;
			if (!loops.has(loop.id)) return;
			loop.waitingForSettle = true;
			try {
				pi.sendUserMessage(loop.prompt, { deliverAs: "followUp" });
			} catch {
				schedule(loop);
			}
		}, loop.intervalMs);
	};

	pi.registerCommand("loop", {
		description: "Repeat a prompt after a custom interval",
		handler: async (args, ctx) => {
			const request = parseLoopRequest(args);
			const loop: ActiveLoop = {
				id: nextId++,
				intervalMs: request.intervalMs,
				prompt: request.prompt,
				waitingForSettle: false,
			};
			loops.set(loop.id, loop);
			schedule(loop);
			ctx.ui.notify(`Loop ${loop.id} scheduled every ${formatDuration(loop.intervalMs)}`, "info");
		},
	});

	pi.registerCommand("loops", {
		description: "List active prompt loops",
		handler: async (_args, ctx) => {
			if (loops.size === 0) {
				ctx.ui.notify("No active loops", "info");
				return;
			}
			const summary = [...loops.values()]
				.map((loop) => `${loop.id}: every ${formatDuration(loop.intervalMs)} - ${loop.prompt}`)
				.join("\n");
			ctx.ui.notify(summary, "info");
		},
	});

	pi.registerCommand("loop-stop", {
		description: "Stop one prompt loop, or all loops when no ID is given",
		handler: async (args, ctx) => {
			const value = args.trim();
			if (!value || value === "all") {
				const count = loops.size;
				for (const loop of [...loops.values()]) clearLoop(loop);
				ctx.ui.notify(`Stopped ${count} loop${count === 1 ? "" : "s"}`, "info");
				return;
			}

			const id = Number.parseInt(value, 10);
			const loop = loops.get(id);
			if (!Number.isInteger(id) || String(id) !== value || !loop) {
				ctx.ui.notify(`Loop ${value} was not found`, "warning");
				return;
			}
			clearLoop(loop);
			ctx.ui.notify(`Stopped loop ${id}`, "info");
		},
	});

	pi.on("agent_settled", () => {
		for (const loop of loops.values()) {
			if (loop.waitingForSettle) schedule(loop);
		}
	});

	pi.on("session_shutdown", () => {
		for (const loop of [...loops.values()]) clearLoop(loop);
	});
}

export default function loopExtension(pi: ExtensionAPI) {
	registerLoopCommands(pi);
}
