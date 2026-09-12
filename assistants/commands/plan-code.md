---
description: "Plan Implementation 📝"
---

## Implementation Plan

Create implementation plan optimised for AI-assisted development.

### Plan Location

Write the plan to `${TMPDIR:-/tmp}/agent-plans/<key>/plan.md`, where `<key>` is one of:

- the lowercased Linear issue key (`ful-123`)
- `owner-repo-N` for a GitHub issue (`/` and `#` flattened to `-`)
- the current branch name with `/` flattened to `-`

The plan is disposable: never commit it and never write it inside the repository. Report the path in the command output.

### Task Structure

| Field | Content |
|-------|---------|
| ID | `<phase>.<number>`: Descriptive name |
| Dependencies | Tasks that must complete first, or "None" |
| Scope | Files/functions to modify |
| Success Criteria | How to verify completion |
| Complexity | XS/S/M/L/XL on the `sizing` skill scale (load `sizing` before assigning) |
| Reuse | Existing code, helpers, or prior work the phase builds on, or "None" |
| Parallel | `Yes` when the phase can run alongside its siblings, else `No` |
| Blocked By | External decisions, approvals, or missing inputs, or "None" |
| Flags | ⚠️ High-risk, 🔍 Needs review, 🧠 Context-intensive |

### Planning Principles

- **Atomic:** Each task completable in one session, independently testable, safely revertible
- **Chunked:** Group 3-5 related tasks; each chunk produces working code
- **Stateless:** Assume fresh AI instance per conversation

### Example

<example>
## Phase 1: Authentication Foundation

### 1.1: Add JWT dependency and configuration
- **Dependencies**: None
- **Scope**: `package.json`, `src/config/auth.ts`
- **Success Criteria**: `npm test` passes, config loads from env
- **Complexity**: XS
- **Reuse**: `src/config/index.ts` env loader
- **Parallel**: No
- **Blocked By**: None

### 1.2: Implement token generation service
- **Dependencies**: 1.1
- **Scope**: `src/services/auth/token.ts`, `src/services/auth/token.test.ts`
- **Success Criteria**: Unit tests pass for sign/verify/refresh
- **Complexity**: S
- **Reuse**: Config from 1.1
- **Parallel**: No
- **Blocked By**: Token expiry values from the security team
- **Flags**: 🔍 Review token expiry values

### 1.3: Add auth middleware
- **Dependencies**: 1.2
- **Scope**: `src/middleware/auth.ts`, `src/middleware/auth.test.ts`
- **Success Criteria**: Protected routes return 401 without valid token
- **Complexity**: M
- **Reuse**: Token service from 1.2, existing `src/middleware/logging.ts` pattern
- **Parallel**: No
- **Blocked By**: None
- **Flags**: ⚠️ Affects all protected endpoints
</example>

### Constraints

- Each task must be independently testable
- Include test file in scope when adding/modifying functionality
- Flag tasks requiring decisions before implementation
- Note when scope may challenge context limits
- The plan file lives only at the Plan Location; never write it inside the repository
