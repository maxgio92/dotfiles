export const meta = {
  name: 'implement-and-review',
  description: 'peter implements a coding task, dastardly reviews the diff, peter fixes blocking findings; re-reviews until clean or a round cap (default 3)',
  phases: [
    { title: 'Implement', detail: 'peter writes the smallest correct change' },
    { title: 'Review', detail: 'dastardly adversarially reviews the change' },
    { title: 'Fix', detail: 'peter applies confirmed blocking findings' },
  ],
}

// The coding task. Pass it as the Workflow `args` (a string, or {task}).
const task = typeof args === 'string' ? args : (args && args.task)
if (!task) {
  log('No task provided. Invoke with the coding task as args, e.g. Workflow({name:"implement-and-review", args:"add a --json flag to foo"}).')
  return { error: 'no task provided' }
}

phase('Implement')
const implementation = await agent(
  `Implement this coding task in the current repository.\n` +
    `Make the smallest correct change, reuse existing code over new abstractions, ` +
    `and run the project's tests and lint before finishing.\n\n` +
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
const allFindings = []

while (round < MAX_ROUNDS) {
  round++

  const diff = await agent(
    `Capture the working-tree diff of the repository this task targets.\n` +
      `First resolve the repo root: use the absolute path named in the task text below; ` +
      `only fall back to the current directory when the task names none.\n` +
      `Do NOT modify the repo or its index: no git add of any kind (in particular no ` +
      `\`git add -N\`, it pollutes the index of whatever directory you run it in).\n` +
      `Run \`git -C <repo> diff HEAD\` for tracked changes, then for each file listed by ` +
      `\`git -C <repo> ls-files --others --exclude-standard\` append ` +
      `\`git diff --no-index -- /dev/null <repo>/<file>\` so new files show too.\n` +
      `Return the combined raw diff as plain text. If it is empty, return the single ` +
      `word NONE. Output nothing else.\n\n` +
      `Task (for locating the repo):\n${task}`,
    { label: `capture-diff:r${round}`, phase: 'Review' },
  )

  phase('Review')
  const review = await agent(
    `Review the change below for the task. Challenge the design and problem framing first, ` +
      `then hunt AI slop, overengineering, leaky abstractions, producer/consumer mixing, ` +
      `and repo-convention breaks. Mark each finding blocking or non-blocking.\n\n` +
      `Task:\n${task}\n\nImplementation summary from peter:\n${implementation}\n\n` +
      `Diff under review (round ${round}):\n${diff}`,
    {
      label: `dastardly:review:r${round}`,
      phase: 'Review',
      agentType: 'dastardly',
      schema: REVIEW_SCHEMA,
    },
  )

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
  await agent(
    `Apply fixes for these confirmed blocking review findings. ` +
      `Smallest correct change; re-run the project's tests and lint after.\n\n${fixList}`,
    { label: `peter:fix:r${round}`, phase: 'Fix', agentType: 'peter' },
  )
  fixedAny = true
  log(`Round ${round}: fixed ${blocking.length} blocking finding(s). Re-reviewing.`)
}

if (!converged) {
  log(`Hit round cap (${MAX_ROUNDS}) with blocking findings still open.`)
}

return {
  implemented: true,
  rounds: round,
  converged,
  fixed: fixedAny,
  findings: allFindings,
}
