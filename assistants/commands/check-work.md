---
description: Refresh the worker table from panes, tickets, PRs, reviews, and current CI
---

Load the `orchestrating-work` skill and run its `/check-work` flow once.
Use `$ARGUMENTS` to limit the check to named tasks or request continued monitoring.
Report unknown status when a source is unavailable. Do not infer completion from idle.
