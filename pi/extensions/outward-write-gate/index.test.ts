import assert from "node:assert/strict";
import test from "node:test";
import { isOutwardWrite } from "./index.ts";

test("gh api with a request field is a write", () => {
	assert.equal(isOutwardWrite("gh api repos/a/b/issues/1/comments -f body=hi"), true);
	assert.equal(isOutwardWrite("gh api repos/a/b/issues/1/comments --field body=hi"), true);
	assert.equal(isOutwardWrite("gh api repos/a/b/pulls/1/comments/2/replies --input -"), true);
	assert.equal(isOutwardWrite("gh api repos/a/b/issues/1/comments -fbody=hi"), true);
	assert.equal(isOutwardWrite("gh api repos/a/b/issues/1/comments -Fbody=@f"), true);
});

test("gh api with an explicit mutating method is a write", () => {
	assert.equal(isOutwardWrite("gh api --method POST repos/a/b/issues"), true);
	assert.equal(isOutwardWrite("gh api -X delete repos/a/b/issues/comments/1"), true);
	assert.equal(isOutwardWrite("gh api -XPOST repos/a/b/issues"), true);
	assert.equal(isOutwardWrite("gh api --method=POST repos/a/b/issues"), true);
});

test("gh api continued across backslash-newline is a write", () => {
	assert.equal(isOutwardWrite("gh api repos/a/b/issues \\\n  --input body.json"), true);
	assert.equal(isOutwardWrite("gh api repos/a/b/issues \\\n  -X POST"), true);
});

test("gh api with a quoted mutating method is a write", () => {
	assert.equal(isOutwardWrite('gh api --method "POST" repos/a/b/issues'), true);
	assert.equal(isOutwardWrite("gh api -X 'DELETE' repos/a/b/issues/comments/1"), true);
});

test("gh api with a quoted pipe before the write flag is a write", () => {
	assert.equal(isOutwardWrite("gh api repos/a/b/issues/1/comments -f body='a|b'"), true);
	assert.equal(isOutwardWrite("gh api repos/a/b/issues -H 'Accept: a|b' -f body=hi"), true);
	assert.equal(isOutwardWrite('gh api repos/a/b/issues -H "X: a;b" -X POST'), true);
	assert.equal(isOutwardWrite("gh api repos/a/b/pulls/1 -H 'Accept: a|b' | gh api -X POST repos/c/d/issues"), true);
});

test("gh api with an escaped quote before the write flag is a write", () => {
	assert.equal(isOutwardWrite('gh api repos/a/b/issues -H "X: a\\"b" -X POST'), true);
	assert.equal(isOutwardWrite('gh api repos/a/b/issues -H "X: a\\"b|c" -f body=x'), true);
	assert.equal(isOutwardWrite("gh api repos/a/b/issues -H 'X: a'\\''b' -f body=x"), true);
});

test("gh api reads are not writes", () => {
	assert.equal(isOutwardWrite("gh api repos/a/b/pulls/1 --jq .title"), false);
	assert.equal(isOutwardWrite("gh api -X GET repos/a/b/pulls/1"), false);
});

test("gh read subcommands are not writes", () => {
	assert.equal(isOutwardWrite("gh pr view 1"), false);
	assert.equal(isOutwardWrite("gh issue list --state all"), false);
	assert.equal(isOutwardWrite("gh workflow list"), false);
});

test("gh mutating subcommands are writes", () => {
	assert.equal(isOutwardWrite("gh pr edit 1 --title x"), true);
	assert.equal(isOutwardWrite("gh pr ready 1"), true);
	assert.equal(isOutwardWrite("gh issue close 3"), true);
	assert.equal(isOutwardWrite("gh release create v1.0.0"), true);
	assert.equal(isOutwardWrite("gh repo edit --description x"), true);
	assert.equal(isOutwardWrite("gh workflow run ci.yml"), true);
});

test("git push with flags between git and the subcommand is a write", () => {
	assert.equal(isOutwardWrite("git -C repo push origin HEAD"), true);
	assert.equal(isOutwardWrite("git status; git log"), false);
});

test("gh-review-reply is a write", () => {
	assert.equal(isOutwardWrite("gh-review-reply https://github.com/a/b/pull/1#discussion_r5 --body-file reply.md"), true);
});
