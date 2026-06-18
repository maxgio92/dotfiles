export const meta = {
  name: 'implement-and-review',
  description: 'peter implements a coding task, dastardly reviews the diff, peter applies the confirmed blocking findings (single pass)',
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

phase('Review')
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
const review = await agent(
  `Review the change just made for the task below. Challenge the design and problem framing first, ` +
    `then hunt AI slop, overengineering, leaky abstractions, producer/consumer mixing, and repo-convention breaks. ` +
    `Mark each finding blocking or non-blocking.\n\n` +
    `Task:\n${task}\n\nImplementation summary from peter:\n${implementation}`,
  { label: 'dastardly:review', phase: 'Review', agentType: 'dastardly', schema: REVIEW_SCHEMA },
)

const findings = review.findings || []
const blocking = findings.filter((f) => f.severity === 'blocking')
if (blocking.length === 0) {
  log(`Review found ${findings.length} finding(s), none blocking. Skipping fix stage.`)
  return { implemented: true, findings, fixed: false }
}

phase('Fix')
const fixList = blocking
  .map((f, i) => `${i + 1}. [${f.file || 'unspecified'}] ${f.title}: ${f.detail}`)
  .join('\n')
const fix = await agent(
  `Apply fixes for these confirmed blocking review findings. ` +
    `Smallest correct change; re-run the project's tests and lint after.\n\n${fixList}`,
  { label: 'peter:fix', phase: 'Fix', agentType: 'peter' },
)

return { implemented: true, findings, fixed: true, fixSummary: fix }
