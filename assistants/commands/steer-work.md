---
description: Route a user instruction to the worker assigned to a task
---

Load the `orchestrating-work` skill and run its `/steer-work` flow.
Use `$ARGUMENTS` as the task ID followed by the user's instruction.
Verify the target and its input state before delivery. Report acknowledgement separately.
