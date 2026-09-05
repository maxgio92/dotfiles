export const meta = {
  name: 'implement-and-review',
  description: 'peter implements a coding task, dastardly reviews the diff through codex (GPT-5 via MCP), peter fixes blocking findings; re-reviews until clean or a round cap (default 3)',
  phases: [
    { title: 'Implement', detail: 'peter writes the smallest correct change' },
    { title: 'Review', detail: 'dastardly reviews via codex (GPT-5), vets its findings' },
    { title: 'Fix', detail: 'peter applies confirmed blocking findings' },
  ],
}

// The coding task. Pass it as the Workflow `args` (a string, or {task}).
const task = typeof args === 'string' ? args : (args && args.task)
if (!task) {
  log('No task provided. Invoke with the coding task as args, e.g. Workflow({name:"implement-and-review", args:"add a --json flag to foo"}).')
  return { error: 'no task provided' }
}

// Optional: diff against this ref instead of HEAD (pass {task, baseRef}).
// Use it when reviewing committed work (e.g. after a rebase), where
// `git diff HEAD` is empty and the review would pass vacuously.
const baseRef = (args && typeof args === 'object' && args.baseRef) || null

phase('Implement')
const implementation = await agent(
  `Implement this coding task in the current repository.\n` +
    `Make the smallest correct change, reuse existing code over new abstractions, ` +
    `and run the project's tests and lint before finishing.\n` +
    `Do not commit, stage, or push; leave every change in the working tree. ` +
    `The orchestrating session commits after the review loop converges.\n\n` +
    `Task:\n${task}`,
  { label: 'peter:implement', phase: 'Implement', agentType: 'peter' },
)

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
  const diff = await agent(
    `Capture the diff of the repository this task targets.\n` +
      `First resolve the repo root: use the absolute path named in the task text below; ` +
      `only fall back to the current directory when the task names none.\n` +
      `Do NOT modify the repo or its index: no git add of any kind (in particular no ` +
      `\`git add -N\`, it pollutes the index of whatever directory you run it in).\n` +
      diffCmd +
      `then for each file listed by ` +
      `\`git -C <repo> ls-files --others --exclude-standard\` append ` +
      `\`git diff --no-index -- /dev/null <repo>/<file>\` so new files show too.\n` +
      `Return the combined raw diff as plain text. If it is empty, return the single ` +
      `word NONE. Output nothing else.\n\n` +
      `Task (for locating the repo):\n${task}`,
    { label: `capture-diff:r${round}`, phase: 'Review' },
  )

  if (!diff || diff.trim() === 'NONE') {
    unverified = true
    log(`Round ${round}: diff capture returned nothing; cannot review. Stopping unverified.`)
    break
  }

  phase('Review')
  const review = await agent(
    `Review the change below for the task. Challenge the design and problem framing first, ` +
      `then hunt AI slop, overengineering, leaky abstractions, producer/consumer mixing, ` +
      `and repo-convention breaks. Mark each finding blocking or non-blocking.\n\n` +
      `MANDATORY: run this review through the codex MCP server (GPT-5) as the reviewing ` +
      `engine. Load the tools with ToolSearch("select:mcp__codex__codex,mcp__codex__codex-reply"), ` +
      `then start ONE session: codex with profile "review" and cwd set to the repo root the ` +
      `task names. Send codex your full review rubric (design challenge, trust boundaries and ` +
      `cross-system semantics, slop, overengineering, test coverage) together with the task ` +
      `and the diff. Codex's first answer is usually a survey: push back at least once with ` +
      `codex-reply where it is generic or hedged. Then vet every codex claim against the ` +
      `actual code yourself before reporting: drop what you can refute, add what it missed, ` +
      `and assign severities with your own judgment. Report only vetted findings.\n` +
      `Fallback: if the codex MCP tools are not available in this session, perform the review ` +
      `yourself and include one extra non-blocking finding titled "codex-unavailable" so the ` +
      `operator can see the engine fell back.\n\n` +
      `Task:\n${task}\n\nImplementation summary from peter:\n${implementation}\n` +
      (fixSummaries.length
        ? `\nFix summaries from earlier rounds:\n${fixSummaries.join('\n---\n')}\n`
        : ``) +
      `\nDiff under review (round ${round}):\n${diff}`,
    {
      label: `dastardly:review:r${round}`,
      phase: 'Review',
      agentType: 'dastardly',
      schema: REVIEW_SCHEMA,
    },
  )

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
  const fixSummary = await agent(
    `Apply fixes for these confirmed blocking review findings. ` +
      `Smallest correct change; re-run the project's tests and lint after. ` +
      `Do not commit, stage, or push; leave every change in the working tree.\n\n${fixList}`,
    { label: `peter:fix:r${round}`, phase: 'Fix', agentType: 'peter' },
  )
  if (fixSummary) fixSummaries.push(`Round ${round}:\n${fixSummary}`)
  fixedAny = true
  log(`Round ${round}: fixed ${blocking.length} blocking finding(s). Re-reviewing.`)
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
}
