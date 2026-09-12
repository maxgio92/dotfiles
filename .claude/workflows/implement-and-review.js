export const meta = {
  name: 'implement-and-review',
  description: 'peter implements a coding task, dastardly reviews the diff through Codex (official plugin) and vets its findings, peter fixes blocking findings; re-reviews until clean or a round cap (default 3)',
  phases: [
    { title: 'Research', detail: 'optional: one agent researches the domain, prior art, and pitfalls before planning (args.research)' },
    { title: 'Plan', detail: 'optional: a planner decomposes large tasks into phases (args.plan)' },
    { title: 'Implement', detail: 'peter writes the smallest correct change' },
    { title: 'Review', detail: 'dastardly reviews through Codex and vets its findings; reviewer "claude" reviews in Claude only' },
    { title: 'Fix', detail: 'peter applies confirmed blocking findings' },
  ],
}

// The coding task. Pass it as the Workflow `args` (a string, or {task}).
const task = typeof args === 'string' ? args : (args && args.task)
if (!task) {
  log('No task provided. Invoke with the coding task as args, e.g. Workflow({name:"implement-and-review", args:"add a --json flag to foo"}).')
  return { error: 'no task provided' }
}

// Optional: repository root (pass {task, repoRoot}). Used for the agent packets
// and the planPath guard. Prefer passing it: guessing the root from the task
// text is unsafe, since the first absolute path in a task body is often a Scope
// or Evidence file, not the repository.
const repoRootArg =
  (args && typeof args === 'object' && typeof args.repoRoot === 'string' && args.repoRoot.trim()) || null

// Fallback repository path guessed from the task text when repoRoot is absent.
// A fix agent may run in a git worktree and, given only the findings, search
// the main checkout instead (seen in run wf_19705886). The first absolute path
// in the task text that a later 'branch', 'worktree', or 'repository' in the
// same sentence qualifies marks that sentence. The candidates are the
// qualifying paths plus any path that prefixes one of them, since a repository
// root is a prefix of its files; the shortest candidate wins ('tests in
// /r/tests/x_test.go for the repository /r' resolves to /r, 'Fix /a/b/c and
// /a/b in the repository /a' to /a). Unrelated paths never compete, so a
// fixture pair ('/home/me/project worktree; fixtures live in /tmp/fx and
// /tmp/fx/case.json') cannot displace the root.
// Then the first absolute path anywhere; else null and the prompts fall back
// to 'the repository this task names'.
const resolveRepoPath = (text) => {
  // A path starts at a word edge so `codex/hooks.json`, URLs, and tilde paths
  // like `~/code/repo` do not match (the latter would resolve to `/code/repo`).
  const ABS_PATH = /(?<![\w.:\/~-])\/[\w.@+-]+(?:\/[\w.@+-]+)*/g
  const trimPath = (m) => m.replace(/[.,;:]+$/, '')
  const sentences = String(text).split(/(?<=[.!?])\s+|\n+/)
  for (const sentence of sentences) {
    const paths = [...sentence.matchAll(ABS_PATH)]
    const qualifying = paths
      .filter((m) => /\b(branch|worktree|repository)\b/i.test(sentence.slice(m.index + m[0].length)))
      .map((m) => trimPath(m[0]))
    if (qualifying.length === 0) continue
    const candidates = paths
      .map((m) => trimPath(m[0]))
      .filter((p) => qualifying.includes(p) || qualifying.some((q) => q.startsWith(p + '/')))
    return candidates.reduce((root, p) => (p.length < root.length ? p : root))
  }
  const first = String(text).match(ABS_PATH)
  return first ? trimPath(first[0]) : null
}
const repoPath = repoRootArg || resolveRepoPath(task)
const repoName = repoPath || 'the repository this task names'

// Packet fields shared by every agent prompt.
const discipline = `Discipline: no preamble, do not restate the task, always return a final report.`
const scopeLine = repoPath ? `Scope: the repository at ${repoPath}.\n` : ``

// Optional: diff against this ref instead of HEAD (pass {task, baseRef}).
// Use it when reviewing committed work (e.g. after a rebase), where
// `git diff HEAD` is empty and the review would pass vacuously.
const baseRef = (args && typeof args === 'object' && args.baseRef) || null

// Optional: planning mode for large tasks (pass {task, plan: true}).
// One planner decomposes the task, then one fresh peter per phase.
const planMode = (args && typeof args === 'object' && args.plan === true) || false

// Optional: plan file (pass {task, plan: true, planPath}).
// When planning runs and returns phases, the plan is written there as Markdown
// so the caller can read or delete it. The path must lie outside the repository
// the task names; a path inside it is skipped with a warning.
const planPath =
  (args && typeof args === 'object' && typeof args.planPath === 'string' && args.planPath.trim()) || null

// Optional: review engine (pass {task, reviewer: 'claude'} to opt out).
// 'codex' (default): dastardly runs one adversarial review through the
// official Codex plugin, with its rubric loaded as a Codex skill, and vets the
// findings before reporting. Falls back to a Claude-only review when Codex
// cannot run.
// 'claude': dastardly reviews in Claude alone.
const reviewer =
  (args && typeof args === 'object' && args.reviewer === 'claude') ? 'claude' : 'codex'

// Optional: research before planning (pass {task, research}).
// true: always run one research agent first.
// false: never run it.
// 'auto' (default): run it when planning mode is set or the task text names a
// new dependency, an external API contract, an unfamiliar domain, or a
// security-sensitive surface.
// A non-empty string is pre-existing research (e.g. from a task tracker); it
// is injected as-is and the phase is skipped.
const rawResearch =
  (args && typeof args === 'object' && args.research !== undefined && args.research !== null)
    ? args.research
    : 'auto'
// A blank string (e.g. an empty tracker field) means "no research supplied",
// not "skip research"; anything else unrecognised falls back to 'auto'.
let research = 'auto'
if (typeof rawResearch === 'boolean' || rawResearch === 'auto') {
  research = rawResearch
} else if (typeof rawResearch === 'string') {
  if (rawResearch.trim()) research = rawResearch
} else {
  log(`Unrecognised research value ${JSON.stringify(rawResearch)}; using 'auto'.`)
}
// Matched on word boundaries so "author" does not trigger on "auth" and
// "tokenizer" does not trigger on "token".
const RESEARCH_SIGNALS = [
  'new dependency', 'new library', 'protocol', 'external api', 'third-party api',
  'webhook', 'unfamiliar', 'security', 'auth', 'authentication', 'authorization',
  'credential', 'token', 'secret', 'crypto',
]
const taskLower = String(task).toLowerCase()
const mentionsSignal = (signal) => {
  const stem = signal.replace(/[-\s]/g, '[-\\s]').replace(/y$/, '(y|ies)')
  return new RegExp(`\\b${stem}(s|es)?\\b`).test(taskLower)
}
const runResearch =
  research === true ||
  (research === 'auto' && (planMode || RESEARCH_SIGNALS.some(mentionsSignal)))

const noCommitRule =
  `Do not commit, stage, or push; leave every change in the working tree. ` +
  `The orchestrating session commits after the review loop converges.`

// One re-request on an empty reply (null, not a schema result) before the
// caller decides what a missing answer means. The full packet is resent so
// every instruction in it (engine, fallback rule, scope) still holds.
const askOnce = async (prompt, opts) => {
  const first = await agent(prompt, opts)
  if (first) return first
  log(`${opts.label} returned nothing; re-requesting once.`)
  return agent(`You returned nothing. Reply in text.\n\n` + prompt, { ...opts, label: `${opts.label}:retry` })
}

let researchResult = null
if (runResearch) {
  phase('Research')
  const RESEARCH_SCHEMA = {
    type: 'object',
    additionalProperties: false,
    properties: {
      findings: { type: 'array', items: { type: 'string' } },
      priorArt: { type: 'array', items: { type: 'string' } },
      pitfalls: { type: 'array', items: { type: 'string' } },
      sources: { type: 'array', items: { type: 'string' }, description: 'URLs or file paths' },
      verdict: { type: 'string', minLength: 1, description: 'one line on whether the task as stated should change' },
    },
    required: ['findings', 'priorArt', 'pitfalls', 'sources', 'verdict'],
  }
  researchResult = await askOnce(
    `Task: research the coding task below before anyone plans or implements it. Apply the ` +
      `\`deep-research\` skill at ${planMode ? 'Standard' : 'Quick'} depth. Cover the ` +
      `task's domain, prior art in this repository and upstream, known pitfalls, and ` +
      `existing helpers the implementer should reuse.\n\n` +
      `Coding task:\n${task}\n\n` +
      `Scope: read ${repoName} read-only; do not modify it. Keep any disposable ` +
      `research plan outside the repository and name its path in sources if you create one.\n` +
      `Output: findings, priorArt, pitfalls, sources, and verdict per the schema. Every ` +
      `source is a URL or a file path. The verdict is one line on whether the task as ` +
      `stated should change.\n` +
      discipline,
    { label: 'research:research', phase: 'Research', schema: RESEARCH_SCHEMA },
  )
  if (!researchResult) {
    log('Research agent returned nothing; continuing without research.')
  }
}

// Research text for the planner and peter prompts: the phase result, the
// string arg, or empty. Sections start with 'Research:' and end before 'Coding task:'.
const researchList = (title, items) =>
  items && items.length ? `${title}:\n${items.map((item) => `- ${item}`).join('\n')}\n` : ``
const researchBlock = researchResult
  ? `Research:\n` +
    researchList('Findings', researchResult.findings) +
    researchList('Prior art', researchResult.priorArt) +
    researchList('Pitfalls', researchResult.pitfalls) +
    researchList('Sources', researchResult.sources) +
    `Verdict: ${researchResult.verdict}\n\n`
  : typeof research === 'string' && research !== 'auto' && research.trim()
    ? `Research:\n${research.trim()}\n\n`
    : ``
const contextBlock = researchBlock ? `Context:\n${researchBlock}` : ``

const topicSweep =
  `Before designing, check repository history and related issues or pull requests ` +
  `for an existing solution, and state in one line what you found.`

let plan = null
if (planMode) {
  phase('Plan')
  const PLAN_SCHEMA = {
    type: 'object',
    additionalProperties: false,
    properties: {
      phases: {
        type: 'array',
        minItems: 2,
        maxItems: 6,
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            title: { type: 'string' },
            goal: { type: 'string' },
          },
          required: ['title', 'goal'],
        },
      },
      sweep: { type: 'string' },
    },
    required: ['phases'],
  }
  plan = await askOnce(
    `Task: plan the coding task below. Decompose it into 2 to 6 sequential phases, each ` +
      `independently implementable by a fresh agent with no memory of the others. ` +
      `Order them so each phase builds only on completed ones, and aim for the ` +
      `smallest total change across all phases. ` +
      `${topicSweep}\n\n` +
      contextBlock +
      `Coding task:\n${task}\n\n` +
      `Scope: read ${repoName} as needed but do not modify it.\n` +
      `Output: phases per the schema, each with a short title and a concrete goal stating ` +
      `what must exist and pass when it is done; the topic sweep result in sweep.\n` +
      discipline,
    { label: 'planner:plan', phase: 'Plan', schema: PLAN_SCHEMA },
  )
  if (!plan) {
    log('Plan agent returned nothing; falling back to single-implementer path.')
  } else if (plan.sweep) {
    log(`Topic sweep: ${plan.sweep}`)
  }
}

// Resolve `.` and `..` segments and collapse repeated slashes without the
// `path` module, which the workflow runtime may not provide.
const normalizePath = (p) => {
  const out = []
  for (const seg of String(p).split('/')) {
    if (seg === '' || seg === '.') continue
    if (seg === '..') out.pop()
    else out.push(seg)
  }
  return '/' + out.join('/')
}

let writtenPath = null
// Workflow args are JSON, not shell: an unexpanded `${TMPDIR:-/tmp}` or a
// relative path would be root-anchored by normalizePath and written somewhere
// the caller did not intend.
const planPathUsable = planPath && planPath.startsWith('/') && !planPath.includes('$')
if (planPath && !planPathUsable) {
  log(`Warning: planPath ${planPath} must be an absolute path with shell variables already expanded; plan not written.`)
}
if (planPathUsable && !plan) {
  log(`planPath ${planPath} given but no plan was produced (plan mode off or planner returned nothing); nothing written.`)
}
if (plan && planPathUsable) {
  const planMarkdown =
    `# Plan\n\n` +
    plan.phases.map((p, i) => `## ${i + 1}. ${p.title}\n\n${p.goal}\n`).join('\n') +
    (plan.sweep ? `\nTopic sweep: ${plan.sweep}\n` : ``)
  const repoRoot = repoRootArg && repoRootArg.startsWith('/') ? normalizePath(repoRootArg) : null
  const target = normalizePath(planPath)
  if (!repoRoot) {
    log(`Warning: no absolute repoRoot given; cannot verify that planPath ${planPath} lies outside the repository; plan not written.`)
  } else if (target === repoRoot || target.startsWith(repoRoot + '/')) {
    log(`Warning: planPath ${planPath} lies inside the repository ${repoRoot}; plan not written.`)
  } else {
    const dir = target.slice(0, target.lastIndexOf('/')) || '/'
    if (typeof require === 'function') {
      // The plan file is a convenience, not the deliverable: a write failure
      // must not abort the run after research and planning already happened.
      try {
        const fs = require('fs')
        fs.mkdirSync(dir, { recursive: true })
        fs.writeFileSync(target, planMarkdown)
        writtenPath = target
      } catch (err) {
        log(`Warning: could not write plan to ${target}: ${err && err.message ? err.message : err}`)
      }
    } else {
      const ack = await askOnce(
        `Task: create the directory ${dir} (and any missing parents), then write the ` +
          `Markdown below to ${target} exactly as given, replacing any existing file.\n` +
          `Scope: ${target} only; do not touch any other path.\n` +
          `Output: the single word DONE.\n` +
          `${discipline}\n\n` +
          planMarkdown,
        { label: 'plan:write', phase: 'Plan' },
      )
      if (ack && ack.trim() === 'DONE') writtenPath = target
      else log(`Plan write agent returned ${JSON.stringify(ack)}; plan may not be on disk.`)
    }
    if (writtenPath) log(`Plan written to ${writtenPath}`)
  }
}

phase('Implement')
let implementation
if (plan) {
  const planOverview = plan.phases
    .map((p, i) => `${i + 1}. ${p.title}: ${p.goal}`)
    .join('\n')
  const phaseSummaries = []
  for (let i = 0; i < plan.phases.length; i++) {
    const p = plan.phases[i]
    const summary = await askOnce(
      `Task: implement one phase of a planned coding task in ${repoName}. ` +
        `Make the smallest correct change for YOUR PHASE ONLY, reuse existing code ` +
        `over new abstractions, and run the project's tests and lint before finishing.\n` +
        `Your phase (${i + 1} of ${plan.phases.length}): ${p.title}\n` +
        `Goal: ${p.goal}\n\n` +
        `Context:\n` +
        `Earlier phases are already applied in the working tree; build on them.\n` +
        researchBlock +
        `Full task:\n${task}\n\n` +
        `Full plan:\n${planOverview}\n` +
        (phaseSummaries.length
          ? `\nCompleted phases:\n${phaseSummaries
              .map((s, j) => `${j + 1}. ${plan.phases[j].title}: ${s.trim().split('\n').filter(Boolean).pop()}`)
              .join('\n')}\n`
          : ``) +
        `\nAuthority: ${noCommitRule}\n` +
        scopeLine +
        `Output: a report under 200 words ending with a one-line summary of what your phase changed.\n` +
        discipline,
      {
        label: `peter:implement:p${i + 1}`,
        phase: 'Implement',
        agentType: 'peter',
      },
    )
    const trimmed = summary && summary.trim()
    phaseSummaries.push(trimmed || '(no summary returned)')
    log(
      trimmed
        ? `Phase ${i + 1}/${plan.phases.length} (${p.title}) done.`
        : `Phase ${i + 1}/${plan.phases.length} (${p.title}) returned no report; the diff review will verify it.`,
    )
  }
  implementation = plan.phases
    .map((p, i) => `Phase ${i + 1} (${p.title}):\n${phaseSummaries[i]}`)
    .join('\n---\n')
} else {
  implementation = await askOnce(
    `Task: implement the coding task below in ${repoName}. ` +
      `Make the smallest correct change, reuse existing code over new abstractions, ` +
      `and run the project's tests and lint before finishing. ` +
      `${topicSweep}\n\n` +
      contextBlock +
      `Coding task:\n${task}\n\n` +
      `Authority: ${noCommitRule}\n` +
      scopeLine +
      `Output: a report under 200 words: what changed and why, files touched, test and lint results.\n` +
      discipline,
    { label: 'peter:implement', phase: 'Implement', agentType: 'peter' },
  )
}

const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['blocking', 'non-blocking'] },
          file: { type: 'string' },
          detail: { type: 'string' },
        },
        required: ['title', 'severity', 'detail'],
      },
    },
  },
  required: ['findings'],
}
const MAX_ROUNDS =
  (args && typeof args === 'object' && Number(args.maxRounds)) || 3

let round = 0
let converged = false
let fixedAny = false
let unverified = false
const allFindings = []
const fixSummaries = []

while (round < MAX_ROUNDS) {
  round++

  const diffCmd = baseRef
    ? `Run \`git -C <repo> diff $(git -C <repo> merge-base ${baseRef} HEAD)\` ` +
      `for committed and working-tree changes since the merge base with ${baseRef}, `
    : `Run \`git -C <repo> diff HEAD\` for tracked changes, `
  const repoHint = repoPath
    ? `<repo> is ${repoPath}.\n`
    : `First resolve <repo>: use the absolute path named in the task text below; ` +
      `only fall back to the current directory when the task names none.\n`
  const diffOutput =
    `Output: the combined raw diff as plain text and nothing else. If it is empty, ` +
    `return the single word NONE.\n`
  const diffPrompt =
    `Task: capture the diff of ${repoName}.\n` +
      `Scope: ${repoHint}` +
      `Do NOT modify the repo or its index: no git add of any kind (in particular no ` +
      `\`git add -N\`, it pollutes the index of whatever directory you run it in).\n` +
      diffCmd +
      `then for each file listed by ` +
      `\`git -C <repo> ls-files --others --exclude-standard\` append ` +
      `\`git diff --no-index -- /dev/null <repo>/<file>\` so new files show too.\n` +
      (repoRootArg ? `` : `\nCoding task (for locating the repo):\n${task}\n\n`) +
      diffOutput +
      discipline
  const diff = await askOnce(diffPrompt, { label: `capture-diff:r${round}`, phase: 'Review' })

  if (!diff || diff.trim() === 'NONE') {
    unverified = true
    log(`Round ${round}: diff capture returned nothing; cannot review. Stopping unverified.`)
    break
  }

  phase('Review')
  const reviewOutput =
    `Output: vetted findings per the schema, each with title, severity (blocking or ` +
    `non-blocking), file when known, and detail; an empty array when nothing is wrong.\n`
  const reviewOptions = {
    label: `dastardly:review:r${round}`,
    phase: 'Review',
    agentType: 'dastardly',
    schema: REVIEW_SCHEMA,
  }
  const reviewPrompt =
    `Task: review the change below for the coding task. Challenge the design and problem framing first, ` +
      `then hunt AI slop, overengineering, leaky abstractions, producer/consumer mixing, ` +
      `and repo-convention breaks. Mark each finding blocking or non-blocking.\n\n` +
      (reviewer === 'codex'
        ? `Second opinion REQUIRED: load the \`codex\` skill and follow its adversarial ` +
          `review and pushback procedure. Run ONE adversarial review through the official ` +
          `Codex plugin from the repo root at ${repoName}. Do not pass --base: peter's work ` +
          `is uncommitted and the plugin's default scope reviews the dirty working tree, ` +
          `while --base would review commits only. ` +
          `Put the skill mentions, the task, peter's summary, and your priorities in the ` +
          `focus text. Push back once where Codex is generic or hedged. Then vet every Codex ` +
          `claim against the actual code yourself before reporting: drop what you can refute, ` +
          `add what it missed, and assign severities with your own judgment. Report only ` +
          `vetted findings.\n` +
          `Fallback: if Codex cannot run, perform the review yourself and include one extra ` +
          `non-blocking finding titled "codex-unavailable" so the operator can see the engine ` +
          `fell back.\n\n`
        : `Review alone; do not consult Codex.\n\n`) +
      `Context:\n` +
      `Coding task:\n${task}\n\nImplementation summary from peter:\n${implementation || '(no report returned)'}\n` +
      (fixSummaries.length
        ? `\nFix summaries from earlier rounds:\n${fixSummaries.join('\n---\n')}\n`
        : ``) +
      `\nScope: the diff below in ${repoName}; read-only, do not modify files or the index.\n` +
      `Diff under review (round ${round}):\n${diff}\n\n` +
      reviewOutput +
      discipline
  const review = await askOnce(reviewPrompt, reviewOptions)

  if (!review) {
    unverified = true
    log(`Round ${round}: review agent returned nothing. Stopping unverified.`)
    break
  }

  const findings = review.findings || []
  allFindings.push(...findings)
  const blocking = findings.filter((f) => f.severity === 'blocking')

  if (blocking.length === 0) {
    converged = true
    log(`Round ${round}: ${findings.length} finding(s), none blocking. Converged.`)
    break
  }

  phase('Fix')
  const fixList = blocking
    .map((f, i) => `${i + 1}. [${f.file || 'unspecified'}] ${f.title}: ${f.detail}`)
    .join('\n')
  const fixSummary = await askOnce(
    `Task: in ${repoName}, apply fixes for these confirmed blocking review findings. ` +
      `Smallest correct change; re-run the project's tests and lint after.\n\n${fixList}\n\n` +
      `Authority: Do not commit, stage, or push; leave every change in the working tree.\n` +
      scopeLine +
      `Output: a report under 200 words: what changed per finding, files touched, test and lint results.\n` +
      discipline,
    { label: `peter:fix:r${round}`, phase: 'Fix', agentType: 'peter' },
  )
  // A silent fix agent may or may not have edited files; only a report counts
  // as a fix, and the next diff review shows what actually changed.
  if (fixSummary && fixSummary.trim()) {
    fixSummaries.push(`Round ${round}:\n${fixSummary}`)
    fixedAny = true
    log(`Round ${round}: fixed ${blocking.length} blocking finding(s). Re-reviewing.`)
  } else {
    log(`Round ${round}: fix agent returned no report for ${blocking.length} blocking finding(s). Re-reviewing.`)
  }
}

if (!converged && !unverified) {
  log(`Hit round cap (${MAX_ROUNDS}) with blocking findings still open.`)
}

const engineFellBack = allFindings.some((f) => f.title === 'codex-unavailable')

return {
  implemented: true,
  rounds: round,
  converged,
  unverified,
  engineFellBack,
  fixed: fixedAny,
  findings: allFindings,
  research: researchResult || (typeof research === 'string' && research !== 'auto' ? research : null),
  planPath: writtenPath || null,
}
