# Code review: dastardly + Codex setup vs Wimpy's review-code pipeline

Date: 2026-09-12
Compared at: dotfiles 09671ab (main), wimpysworld/nix-config main (skill last substantively changed 2026-09-05)
Method: deep-research, Standard depth (4 plan items, 12 sources: 5 local files, 7 upstream files plus commit history)

## Summary

The two setups answer different questions. Ours asks "is this change correct and well designed" and gets its rigor from one adversarial specialist cross-checked by a second model (GPT-5 via the official Codex plugin) [1][2][3]. Wimpy's asks "is this review trustworthy enough to post under my name" and gets its rigor from process: parallel sub-agent lanes, a pressure-test round on every blocking finding, durable run-scoped reports, and a three-stage review, draft, post pipeline with SHA guards [5][8][9]. The 152b8be..09671ab pull moved dastardly off Go-only review and onto the Codex plugin as the default engine [2][3]; Wimpy's two commits on 2026-09-11 were housekeeping (frontmatter moved to header.toml, storage mechanics deduplicated into review-report-path) [12].

## Findings

### What changed on each side

The pull made three substantive changes: dastardly is now language-general, loading `effective-go` only when `.go` files are present and otherwise deferring to whatever standards skill the repository names [1]; Codex became the default review engine for both `/code-review` and the implement-and-review workflow, with "Claude only" / `reviewer: 'claude'` as the opt-out [2][4]; and the Codex transport moved from the removed MCP server to the official `codex@openai-codex` plugin's companion script, with a defined `codex-unavailable` fallback nit instead of a hard failure [3]. KEY: this setup now always runs two models over every non-trivial review by default.

Wimpy's skill was last substantively changed on 2026-09-05; the 2026-09-11 commits only split metadata into `header.toml` and moved the report-path template out of the skill into `review-report-path` [12].

### Architecture

Ours is a two-model, single-reviewer design: `/code-review` launches dastardly, which runs one adversarial review through Codex with the shared rubric loaded as a Codex skill, pushes back once on hedged output, then vets every Codex claim against the code and assigns severities by its own definitions [2][3]. Wimpy's is a one-model, many-agent design: an orchestrating command fans out single-lane sub-agents by concern (security lanes go to the `dibble` auditor), each with a short 3-4 target attack packet, and re-requests once from any lane that goes idle [5][9]. Cross-model diversity catches what one model family misses; their lane parallelism covers large diffs one context cannot hold. Neither has the other's mechanism.

### False-positive control

Both run a structurally similar two-pass filter. Ours: Codex proposes, dastardly refutes ("drop what you can refute, add what it missed") on top of dastardly's own evidence rules (trace callers, never infer from API shape) [1][3][4]. Wimpy's: sub-agents propose, then the orchestrator sends each medium-or-higher finding back to its raising agent to verify preconditions against deployment reality (what executes where, isolation, what gets logged), downgrading findings whose preconditions fail [5]. CAVEAT: our vetting checks findings against the code; theirs also checks against the deployed configuration, a lens the dastardly rubric does not name.

### Output and persistence

Dastardly delivers a structured in-chat verdict: design block up front, four severities, ready-to-post `Suggested comment` per finding [1]. Wimpy's skill forbids exactly that: the report states no verdict and drafts no comment; `draft-code-review` owns the comment (Findings section only, three sentences per finding), and `post-code-review` is the sole mutating step, guarded by a head-SHA comparison and an explicit confirmation, with `--request-changes` deliberately excluded as the human's call [5][8][9]. Their reports persist under `~/.local/state/agent-reviews/<project>/<target>/run-<timestamp>/` with the reviewed SHA recorded [7]; we have an equivalent convention in the `review-reports` skill (`~/reports/<repo>/<date>-<agent>-<slug>.md` with the SHA) [6], but `/code-review` never invokes it, so reviews remain session-only. That gap survived the pull.

### Scope resolution and lenses

Wimpy resolves six input shapes to a diff via an explicit table (PR, branch, default branch, worktree, commit, none) and parameterises the review with caller-supplied lens and severity bar through four thin commands (`review-code-mine/-colleague/-community/-again`), the last one rechecking a prior report against the author's response [5][9][12]. Our command accepts "a PR URL, branch name, base ref, directory, or file list" in one prose line with no per-case diff rule, and has one fixed lens [2]. The workflow does have a `baseRef` arg for committed work, but only inside implement-and-review [4].

### Voice and downstream reuse

Their findings are written from the start in `contribution-voice` (hard budgets: three sentences per finding, no scaffolding) because they will be posted under the user's name [5][10]. Our equivalent register lives in `pr-review-message` and the `publish` gate, but dastardly's `Suggested comment` field is not wired to either; it is a convenience string, not a pipeline stage.

## Interesting findings

- The convergence is mutual: before the pull we had a Go-only reviewer and they had inline storage rules; now our reviewer is language-general (their skill was always language-agnostic) and their storage is factored into a dedicated skill (we already had one) [1][7][12].
- Their lane-packet sizing rule ("a long multi-target packet correlates with a sub-agent stalling and returning nothing") and the lost-reply fallback files come from fixes in their git history (commits 730940f1, 60ff163a), so those process rules are scar tissue, not theory [12].
- Our implement-and-review workflow already encodes what their pipeline splits into three commands: review, fix, re-review to convergence with a round cap, and commit boundaries in the orchestrator [4]. Their pipeline instead optimises for reviews of other people's PRs, which the `upstream-contribution` skill covers separately.

## What each could borrow

For us, three items, in value order:

1. Wire `/code-review` to the `review-reports` skill and record the reviewed SHA (the convention exists; it is unused) [2][6].
2. Add their deployment-reality precondition check to dastardly's vetting step for block-severity findings [5].
3. Adopt their input-resolution table, including the "default branch with nothing unpushed: stop and ask" rule [5].

For them: our cross-model second opinion with vetting, and our closed fix loop; their pipeline reviews and posts but never repairs [3][4][9].

## Sources

Local (dotfiles at 09671ab):

[1] assistants/agents/dastardly.md: the reviewer, now language-general
[2] assistants/commands/code-review.md: the /code-review command, Codex-by-default
[3] assistants/skills/codex/SKILL.md: Codex plugin transport, pushback turn, fallback
[4] .claude/workflows/implement-and-review.js: review/fix loop, reviewer opt-out, baseRef
[6] assistants/skills/review-reports/SKILL.md: the unused report-storage convention

Upstream (wimpysworld/nix-config, main):

[5] [review-code SKILL.md](https://github.com/wimpysworld/nix-config/blob/main/home-manager/_mixins/agentic/assistants/skills/review-code/SKILL.md): the compared skill
[7] [review-report-path SKILL.md](https://github.com/wimpysworld/nix-config/blob/main/home-manager/_mixins/agentic/assistants/skills/review-report-path/SKILL.md): run-scoped report storage
[8] [post-code-review prompt.md](https://github.com/wimpysworld/nix-config/blob/main/home-manager/_mixins/agentic/assistants/agents/donatello/commands/post-code-review/prompt.md): SHA guard, confirm-then-post, no request-changes
[9] [draft-code-review prompt.md](https://github.com/wimpysworld/nix-config/blob/main/home-manager/_mixins/agentic/assistants/agents/donatello/commands/draft-code-review/prompt.md) plus review-code-* commands: draft stage and lens-supplying callers
[10] [contribution-voice SKILL.md](https://github.com/wimpysworld/nix-config/blob/main/home-manager/_mixins/agentic/assistants/skills/contribution-voice/SKILL.md): length budgets so posts read human-written
[11] [dibble prompt.md](https://github.com/wimpysworld/nix-config/blob/main/home-manager/_mixins/agentic/assistants/agents/dibble/prompt.md): the security lane specialist
[12] [Commit history of review-code SKILL.md](https://api.github.com/repos/wimpysworld/nix-config/commits?path=home-manager/_mixins/agentic/assistants/skills/review-code/SKILL.md): 2026-09-11 commits are housekeeping only
