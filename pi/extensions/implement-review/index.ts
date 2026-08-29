import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { ThinkingLevel } from "@earendil-works/pi-agent-core";
import {
	BorderedLoader,
	type ExtensionAPI,
	getAgentDir,
	parseFrontmatter,
	withFileMutationQueue,
} from "@earendil-works/pi-coding-agent";
import {
	CODE_REVIEW_COMMAND,
	IMPLEMENT_REVIEW_COMMANDS,
	isConverged,
	parseStructuredReview,
	parseWorkflowArgs,
	type ReviewFinding,
	type StructuredReview,
} from "./logic.ts";

const MAX_DIFF_BYTES = 1024 * 1024;
const PETER_MODEL = "anthropic/claude-fable-5";
const DASTARDLY_MODEL = "openai-codex/gpt-5.6-sol";
const REVIEW_OUTPUT_EXTENSION = path.join(path.dirname(fileURLToPath(import.meta.url)), "review-output.ts");
const COMMUNICATION_RULES_EXTENSION = path.resolve(
	path.dirname(fileURLToPath(import.meta.url)),
	"../communication-rules/index.ts",
);

interface AgentDefinition {
	name: string;
	systemPrompt: string;
	model?: string;
}

interface DispatchDefaults {
	model?: string;
	thinkingLevel?: ThinkingLevel;
}

interface ChildResult {
	output: string;
	review?: StructuredReview;
	reviewSubmissions: number;
	stderr: string;
	exitCode: number;
	stopReason?: string;
	errorMessage?: string;
}

interface ReviewResult {
	round: number;
	review: StructuredReview;
}

interface WorkflowResult {
	task: string;
	repoRoot: string;
	implementation: string;
	reviews: ReviewResult[];
	fixes: string[];
	converged: boolean;
	maxRounds: number;
}

interface StandaloneReviewResult {
	repoRoot: string;
	scope: string;
	output: string;
}

type AgentFrontmatter = {
	name?: unknown;
	model?: unknown;
};

interface ProcessResult {
	stdout: string;
	stderr: string;
	exitCode: number;
}

function loadAgent(name: string): AgentDefinition {
	const filePath = path.join(getAgentDir(), "agents", `${name}.md`);
	let content: string;
	try {
		content = fs.readFileSync(filePath, "utf8");
	} catch (error) {
		throw new Error(`Cannot read ${name} agent at ${filePath}: ${error instanceof Error ? error.message : error}`);
	}

	const { frontmatter, body } = parseFrontmatter<AgentFrontmatter>(content);
	if (frontmatter.name !== name) {
		throw new Error(`Agent ${filePath} must declare name: ${name}`);
	}
	return {
		name,
		systemPrompt: body,
		model: typeof frontmatter.model === "string" ? frontmatter.model : undefined,
	};
}

function getPiInvocation(args: string[]): { command: string; args: string[] } {
	const currentScript = process.argv[1];
	const isBunVirtualScript = currentScript?.startsWith("/$bunfs/root/");
	if (currentScript && !isBunVirtualScript && fs.existsSync(currentScript)) {
		return { command: process.execPath, args: [currentScript, ...args] };
	}

	const execName = path.basename(process.execPath).toLowerCase();
	if (!/^(node|bun)(\.exe)?$/.test(execName)) return { command: process.execPath, args };
	return { command: "pi", args };
}

async function runProcess(
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

async function writePromptToTempFile(agentName: string, prompt: string): Promise<{ dir: string; filePath: string }> {
	const dir = await fs.promises.mkdtemp(path.join(os.tmpdir(), "pi-implement-review-"));
	const filePath = path.join(dir, `${agentName}.md`);
	await withFileMutationQueue(filePath, async () => {
		await fs.promises.writeFile(filePath, prompt, { encoding: "utf8", mode: 0o600 });
	});
	return { dir, filePath };
}

async function runAgent(
	agent: AgentDefinition,
	task: string,
	cwd: string,
	defaults: DispatchDefaults,
	signal?: AbortSignal,
): Promise<string> {
	const result = await runAgentProcess(agent, task, cwd, defaults, signal);
	if (!result.output.trim()) throw new Error(`${agent.name} returned no output`);
	return result.output.trim();
}

async function runReviewAgent(
	agent: AgentDefinition,
	task: string,
	cwd: string,
	defaults: DispatchDefaults,
	signal?: AbortSignal,
): Promise<StructuredReview> {
	const result = await runAgentProcess(agent, task, cwd, defaults, signal, [REVIEW_OUTPUT_EXTENSION]);
	if (!result.review || result.reviewSubmissions !== 1) {
		throw new Error(
			`${agent.name} must call submit_review exactly once; received ${result.reviewSubmissions} valid submission(s)`,
		);
	}
	return result.review;
}

async function runAgentProcess(
	agent: AgentDefinition,
	task: string,
	cwd: string,
	defaults: DispatchDefaults,
	signal?: AbortSignal,
	extensions: string[] = [],
): Promise<ChildResult> {
	const args = ["--mode", "json", "-p", "--no-session", "--no-context-files", "--no-extensions"];
	const inheritsModel = !agent.model;
	const model = agent.model ?? defaults.model;
	if (model) args.push("--model", model);
	if (inheritsModel && defaults.thinkingLevel) args.push("--thinking", defaults.thinkingLevel);
	for (const extension of [COMMUNICATION_RULES_EXTENSION, ...extensions]) args.push("--extension", extension);

	const temp = await writePromptToTempFile(agent.name, agent.systemPrompt);
	try {
		args.push("--append-system-prompt", temp.filePath);
		const invocation = getPiInvocation(args);
		const processResult = await runProcess(invocation.command, invocation.args, cwd, signal, `Task: ${task}\n`);
		const result = parseChildOutput(processResult);
		if (result.exitCode !== 0 || result.stopReason === "error" || result.stopReason === "aborted") {
			throw new Error(
				`${agent.name} failed: ${result.errorMessage || result.stderr.trim() || result.output || "unknown error"}`,
			);
		}
		return result;
	} finally {
		await fs.promises.rm(temp.dir, { recursive: true, force: true });
	}
}

function parseChildOutput(result: ProcessResult): ChildResult {
	let output = "";
	let review: StructuredReview | undefined;
	let reviewSubmissions = 0;
	let stopReason: string | undefined;
	let errorMessage: string | undefined;

	for (const line of result.stdout.split("\n")) {
		if (!line.trim()) continue;
		let event: any;
		try {
			event = JSON.parse(line);
		} catch {
			continue;
		}
		if (event.type !== "message_end" || event.message?.role !== "assistant") continue;
		const content = event.message.content ?? [];
		const text = content
			?.filter((part: any) => part.type === "text")
			.map((part: any) => part.text)
			.join("\n");
		if (text) output = text;
		for (const part of content) {
			if (part.type === "toolCall" && part.name === "submit_review") {
				const parsed = parseStructuredReview(part.arguments);
				if (parsed) {
					review = parsed;
					reviewSubmissions++;
				}
			}
		}
		if (event.message.stopReason) stopReason = event.message.stopReason;
		if (event.message.errorMessage) errorMessage = event.message.errorMessage;
	}

	return { output, review, reviewSubmissions, stderr: result.stderr, exitCode: result.exitCode, stopReason, errorMessage };
}

async function git(args: string[], cwd: string, signal?: AbortSignal, acceptedExitCodes = [0]): Promise<string> {
	const result = await runProcess("git", args, cwd, signal);
	if (!acceptedExitCodes.includes(result.exitCode)) {
		throw new Error(`git ${args.join(" ")} failed: ${result.stderr.trim() || `exit ${result.exitCode}`}`);
	}
	return result.stdout;
}

async function captureDiff(cwd: string, signal?: AbortSignal): Promise<{ repoRoot: string; diff: string }> {
	const repoRoot = (await git(["rev-parse", "--show-toplevel"], cwd, signal)).trim();
	let diff = await git(["diff", "HEAD", "--"], repoRoot, signal);
	const untracked = (await git(["ls-files", "-z", "--others", "--exclude-standard"], repoRoot, signal))
		.split("\0")
		.filter(Boolean);

	for (const relativePath of untracked) {
		const absolutePath = path.join(repoRoot, relativePath);
		diff += await git(["diff", "--no-index", "--", "/dev/null", absolutePath], repoRoot, signal, [0, 1]);
	}
	if (!diff.trim()) throw new Error("Implementation produced no working-tree diff");
	if (Buffer.byteLength(diff, "utf8") > MAX_DIFF_BYTES) {
		throw new Error(`Working-tree diff exceeds ${MAX_DIFF_BYTES} bytes; narrow the task before reviewing`);
	}
	return { repoRoot, diff };
}

async function runWorkflow(
	task: string,
	maxRounds: number,
	cwd: string,
	defaults: DispatchDefaults,
	signal: AbortSignal,
	setStage: (stage: string) => void,
): Promise<WorkflowResult> {
	const peter = { ...loadAgent("peter"), model: PETER_MODEL };
	const dastardly = { ...loadAgent("dastardly"), model: DASTARDLY_MODEL };

	setStage("Peter implementing");
	const implementation = await runAgent(
		peter,
		`Implement this coding task in the current repository. Make the smallest correct change, preserve unrelated working-tree changes, and run focused tests and lint before finishing.\n\nTask:\n${task}`,
		cwd,
		defaults,
		signal,
	);

	const reviews: ReviewResult[] = [];
	const fixes: string[] = [];
	let repoRoot = cwd;

	for (let round = 1; round <= maxRounds; round++) {
		setStage(`Capturing diff for review ${round}/${maxRounds}`);
		const captured = await captureDiff(cwd, signal);
		repoRoot = captured.repoRoot;

		setStage(`Dastardly reviewing ${round}/${maxRounds}`);
		const priorFix = fixes.at(-1) ?? "No fix round has run yet.";
		const review = await runReviewAgent(
			dastardly,
			`Review the current change for the task below. This is a read-only review: do not modify files or the index. Independently inspect repository context and vet every claim against the code. For this workflow, the submit_review tool contract replaces Dastardly's prose Output Format. Call submit_review exactly once with the complete findings array, then stop. Map Dastardly design and block findings to severity "blocking". Map strong and nit findings to "non-blocking". Submit an empty findings array when no findings exist. Do not report a prose verdict.\n\nTask:\n${task}\n\nInitial implementation report:\n${implementation}\n\nLatest fix report:\n${priorFix}\n\nDiff under review (round ${round}):\n${captured.diff}`,
			repoRoot,
			defaults,
			signal,
		);
		reviews.push({ round, review });

		if (isConverged(review)) {
			return { task, repoRoot, implementation, reviews, fixes, converged: true, maxRounds };
		}
		if (round === maxRounds) break;

		setStage(`Peter fixing review ${round}/${maxRounds}`);
		const blockingReview = {
			findings: review.findings.filter((finding) => finding.severity === "blocking"),
		};
		const fixOutput = await runAgent(
			peter,
			`Vet the structured review below against the current code. Apply every confirmed blocking finding using the smallest correct change. Explicitly reject incorrect findings. Preserve unrelated working-tree changes and rerun focused tests and lint.\n\nOriginal task:\n${task}\n\nBlocking findings from review round ${round}:\n${JSON.stringify(blockingReview, null, 2)}`,
			repoRoot,
			defaults,
			signal,
		);
		fixes.push(fixOutput);
	}

	return { task, repoRoot, implementation, reviews, fixes, converged: false, maxRounds };
}

function formatResult(result: WorkflowResult): string {
	const finalReview = result.reviews.at(-1)!;
	const blocking = finalReview.review.findings.filter((finding) => finding.severity === "blocking").length;
	const heading = result.converged
		? `Implement-and-review converged in ${result.reviews.length} review round(s).`
		: `Implement-and-review hit the ${result.maxRounds}-round cap with blocking findings open.`;
	return [
		heading,
		`Repository: ${result.repoRoot}`,
		`Final findings: ${finalReview.review.findings.length} total, ${blocking} blocking`,
		"",
		`## Final review (round ${finalReview.round})`,
		"",
		formatFindings(finalReview.review.findings),
	].join("\n");
}

function formatFindings(findings: ReviewFinding[]): string {
	if (findings.length === 0) return "No findings.";
	return findings
		.map((finding, index) => {
			const location = finding.file ? ` (${finding.file})` : "";
			return `${index + 1}. **${finding.severity}: ${finding.title}**${location}\n\n${finding.detail}`;
		})
		.join("\n\n");
}

export default function implementReviewExtension(pi: ExtensionAPI) {
	const implementCommand: Parameters<ExtensionAPI["registerCommand"]>[1] = {
		description: "Peter implements and fixes until Dastardly reports no blocking findings",
		handler: async (args, ctx) => {
			if (ctx.mode !== "tui") {
				ctx.ui.notify("implement-review currently requires interactive mode", "error");
				return;
			}
			if (!ctx.model) {
				ctx.ui.notify("Select and authenticate a model before running this workflow", "error");
				return;
			}

			let parsed: { task: string; maxRounds: number };
			try {
				parsed = parseWorkflowArgs(args);
			} catch (error) {
				ctx.ui.notify(error instanceof Error ? error.message : String(error), "error");
				return;
			}

			const result = await ctx.ui.custom<WorkflowResult | Error>((tui, theme, _kb, done) => {
				const loader = new BorderedLoader(tui, theme, "Running Peter and Dastardly...");
				loader.onAbort = () => done(new Error("Workflow cancelled"));
				const setStage = (stage: string) => ctx.ui.setStatus("implement-review", stage);
				const defaults: DispatchDefaults = {
					model: `${ctx.model!.provider}/${ctx.model!.id}`,
					thinkingLevel: ctx.thinkingLevel,
				};

				runWorkflow(parsed.task, parsed.maxRounds, ctx.cwd, defaults, loader.signal, setStage)
					.then(done)
					.catch((error) => done(error instanceof Error ? error : new Error(String(error))));
				return loader;
			});
			ctx.ui.setStatus("implement-review", undefined);

			if (result instanceof Error) {
				ctx.ui.notify(result.message, result.message === "Workflow cancelled" ? "info" : "error");
				return;
			}

			pi.sendMessage({
				customType: "implement-review-result",
				content: formatResult(result),
				display: true,
				details: result,
			});
		},
	};

	for (const command of IMPLEMENT_REVIEW_COMMANDS) pi.registerCommand(command, implementCommand);
	pi.registerCommand(CODE_REVIEW_COMMAND, {
		description: "Dastardly reviews a PR, diff, files, or the current branch",
		handler: async (args, ctx) => {
			if (ctx.mode !== "tui") {
				ctx.ui.notify("code-review currently requires interactive mode", "error");
				return;
			}

			const scope = args.trim() || "Review the current branch against its merge base.";
			const result = await ctx.ui.custom<StandaloneReviewResult | Error>((tui, theme, _kb, done) => {
				const loader = new BorderedLoader(tui, theme, "Running Dastardly...");
				loader.onAbort = () => done(new Error("Review cancelled"));
				ctx.ui.setStatus("code-review", "Dastardly reviewing");
				const defaults: DispatchDefaults = {
					model: ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : undefined,
					thinkingLevel: ctx.thinkingLevel,
				};

				(async () => {
					const repoRoot = (await git(["rev-parse", "--show-toplevel"], ctx.cwd, loader.signal)).trim();
					const dastardly = { ...loadAgent("dastardly"), model: DASTARDLY_MODEL };
					const output = await runAgent(
						dastardly,
						`Review the scope. Do not modify files or the index. Apply Dastardly's design, evidence, severity, and output rules.\n\nScope:\n${scope}`,
						repoRoot,
						defaults,
						loader.signal,
					);
					return { repoRoot, scope, output };
				})()
					.then(done)
					.catch((error) => done(error instanceof Error ? error : new Error(String(error))));
				return loader;
			});
			ctx.ui.setStatus("code-review", undefined);

			if (result instanceof Error) {
				ctx.ui.notify(result.message, result.message === "Review cancelled" ? "info" : "error");
				return;
			}

			pi.sendMessage({
				customType: "code-review-result",
				content: result.output,
				display: true,
				details: result,
			});
		},
	});
}
