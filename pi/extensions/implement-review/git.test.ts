import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import test from "node:test";
import { captureDiff, EMPTY_TREE } from "./git.ts";

function initRepo(): { repo: string; startHead: string } {
	const repo = fs.mkdtempSync(path.join(os.tmpdir(), "implement-review-git-test-"));
	const git = (...args: string[]) => execFileSync("git", ["-C", repo, ...args], { encoding: "utf8" });
	git("init", "-q");
	git("config", "user.email", "test@example.invalid");
	git("config", "user.name", "test");
	fs.writeFileSync(path.join(repo, "main.go"), "package main\n");
	git("add", "main.go");
	git("commit", "-q", "-m", "init");
	return { repo, startHead: git("rev-parse", "HEAD").trim() };
}

test("captureDiff sees changes the implementer committed", async (t) => {
	const { repo, startHead } = initRepo();
	t.after(() => fs.rmSync(repo, { recursive: true, force: true }));
	const git = (...args: string[]) => execFileSync("git", ["-C", repo, ...args], { encoding: "utf8" });

	fs.writeFileSync(path.join(repo, "main.go"), "package main\n\nfunc main() {}\n");
	git("add", "main.go");
	git("commit", "-q", "-m", "implement");
	fs.writeFileSync(path.join(repo, "untracked.go"), "package main\n");

	const headOnly = await captureDiff(repo, undefined, {});
	assert.doesNotMatch(headOnly.diff, /func main\(\) \{\}/);

	const { diff } = await captureDiff(repo, undefined, { startHead });
	assert.match(diff, /func main\(\) \{\}/);
	assert.match(diff, /untracked\.go/);
});

test("captureDiff reports the starting commit when nothing changed", async (t) => {
	const { repo, startHead } = initRepo();
	t.after(() => fs.rmSync(repo, { recursive: true, force: true }));

	await assert.rejects(
		() => captureDiff(repo, undefined, { startHead }),
		new RegExp(`no diff against starting commit ${startHead}`),
	);
});

test("captureDiff diffs from the empty tree in a repo with no commits", async (t) => {
	const repo = fs.mkdtempSync(path.join(os.tmpdir(), "implement-review-git-test-"));
	t.after(() => fs.rmSync(repo, { recursive: true, force: true }));
	const git = (...args: string[]) => execFileSync("git", ["-C", repo, ...args], { encoding: "utf8" });
	git("init", "-q");
	git("config", "user.email", "test@example.invalid");
	git("config", "user.name", "test");

	fs.writeFileSync(path.join(repo, "committed.go"), "package main\n");
	git("add", "committed.go");
	git("commit", "-q", "-m", "implement");
	fs.writeFileSync(path.join(repo, "untracked.go"), "package main\n");

	const { diff } = await captureDiff(repo, undefined, { startHead: EMPTY_TREE });
	assert.match(diff, /committed\.go/);
	assert.match(diff, /untracked\.go/);
});

test("captureDiff resolves an explicit base ref through the merge base", async (t) => {
	const { repo } = initRepo();
	t.after(() => fs.rmSync(repo, { recursive: true, force: true }));
	const git = (...args: string[]) => execFileSync("git", ["-C", repo, ...args], { encoding: "utf8" });

	git("branch", "target");
	fs.writeFileSync(path.join(repo, "feature.go"), "package main\n");
	git("add", "feature.go");
	git("commit", "-q", "-m", "feature");

	const { diff } = await captureDiff(repo, undefined, { baseRef: "target" });
	assert.match(diff, /feature\.go/);
});
