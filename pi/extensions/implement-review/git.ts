import { spawn } from "node:child_process";
import * as path from "node:path";

const MAX_DIFF_BYTES = 1024 * 1024;

export interface ProcessResult {
	stdout: string;
	stderr: string;
	exitCode: number;
}

export async function runProcess(
	command: string,
	args: string[],
	cwd: string,
	signal?: AbortSignal,
	stdin?: string,
): Promise<ProcessResult> {
	return new Promise((resolve, reject) => {
		const child = spawn(command, args, {
			cwd,
			shell: false,
			stdio: [stdin === undefined ? "ignore" : "pipe", "pipe", "pipe"],
		});
		let stdout = "";
		let stderr = "";
		let aborted = false;

		const abort = () => {
			aborted = true;
			child.kill("SIGTERM");
			const timer = setTimeout(() => child.kill("SIGKILL"), 5000);
			timer.unref();
		};
		if (signal?.aborted) abort();
		else signal?.addEventListener("abort", abort, { once: true });

		child.stdout.on("data", (data) => {
			stdout += data.toString();
		});
		child.stderr.on("data", (data) => {
			stderr += data.toString();
		});
		child.on("error", reject);
		child.on("close", (code) => {
			signal?.removeEventListener("abort", abort);
			if (aborted) reject(new Error("Workflow cancelled"));
			else resolve({ stdout, stderr, exitCode: code ?? 1 });
		});

		if (stdin !== undefined) child.stdin.end(stdin);
	});
}

export async function git(
	args: string[],
	cwd: string,
	signal?: AbortSignal,
	acceptedExitCodes = [0],
): Promise<string> {
	const result = await runProcess("git", args, cwd, signal);
	if (!acceptedExitCodes.includes(result.exitCode)) {
		throw new Error(`git ${args.join(" ")} failed: ${result.stderr.trim() || `exit ${result.exitCode}`}`);
	}
	return result.stdout;
}

export interface CaptureDiffOptions {
	/** Explicit ref to diff against; resolved through its merge base with HEAD. */
	baseRef?: string;
	/** Commit recorded before the implementer ran; covers commits it made. */
	startHead?: string;
}

export async function captureDiff(
	cwd: string,
	signal?: AbortSignal,
	options: CaptureDiffOptions = {},
): Promise<{ repoRoot: string; diff: string }> {
	const repoRoot = (await git(["rev-parse", "--show-toplevel"], cwd, signal)).trim();
	// Diffing against a pre-implementation commit or merge base instead of
	// HEAD covers work the implementer committed; against HEAD the working
	// tree is clean and a review of the empty diff would converge vacuously.
	const diffBase = options.baseRef
		? (await git(["merge-base", options.baseRef, "HEAD"], repoRoot, signal)).trim()
		: (options.startHead ?? "HEAD");
	let diff = await git(["diff", diffBase, "--"], repoRoot, signal);
	const untracked = (await git(["ls-files", "-z", "--others", "--exclude-standard"], repoRoot, signal))
		.split("\0")
		.filter(Boolean);

	for (const relativePath of untracked) {
		const absolutePath = path.join(repoRoot, relativePath);
		diff += await git(["diff", "--no-index", "--", "/dev/null", absolutePath], repoRoot, signal, [0, 1]);
	}
	if (!diff.trim()) {
		throw new Error(
			options.baseRef
				? `No diff against the merge base with ${options.baseRef}`
				: `Implementation produced no diff against ${options.startHead ? `starting commit ${diffBase}` : "HEAD"}`,
		);
	}
	if (Buffer.byteLength(diff, "utf8") > MAX_DIFF_BYTES) {
		throw new Error(`Diff exceeds ${MAX_DIFF_BYTES} bytes; narrow the task before reviewing`);
	}
	return { repoRoot, diff };
}
