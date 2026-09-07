Alias of implement-review. Run the implement-and-review loop on this task:
$ARGUMENTS

1. Apply the peter skill: implement the smallest correct change, run the
   repository's build, tests, and lint. Do not commit, stage, or push.
2. Apply the dastardly skill to the working-tree diff (`git diff HEAD` plus
   untracked files): challenge the design first, mark each finding blocking or
   non-blocking, report only evidence-backed findings.
3. Apply the peter skill again to fix confirmed blocking findings, then
   re-review. Repeat until a review has no blocking findings or three rounds
   are done.

Report rounds, convergence, and the final findings. Leave every change
uncommitted; the human decides commit and push.
