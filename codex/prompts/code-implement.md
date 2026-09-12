Alias of implement-review. Run the implement-and-review loop on this task:
$ARGUMENTS

1. When the task names a new dependency, external API, unfamiliar domain, or
   security surface, or asks for research, apply the deep-research skill at
   Quick depth first and report findings, prior art, pitfalls, sources, and a
   one-line verdict on whether the task should change. When the task text
   already carries research, use it instead. Feed the result to the next step.
2. Apply the peter skill: implement the smallest correct change, run the
   repository's build, tests, and lint. Do not commit, stage, or push.
3. Apply the dastardly skill to the working-tree diff (`git diff HEAD` plus
   untracked files): challenge the design first, mark each finding blocking or
   non-blocking, report only evidence-backed findings.
4. Apply the peter skill again to fix confirmed blocking findings, then
   re-review. Repeat until a review has no blocking findings or three rounds
   are done.

Report rounds, convergence, and the final findings. Leave every change
uncommitted; the human decides commit and push.
