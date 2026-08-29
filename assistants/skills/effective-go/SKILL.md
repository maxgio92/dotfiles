---
name: effective-go
description: Apply Go best practices, idioms, and conventions from golang.org/doc/effective_go when writing, reviewing, or refactoring Go code.
source: https://github.com/openshift/hypershift/tree/main/.claude/skills/effective-go
---

# Effective Go

Apply the official [Effective Go guide](https://go.dev/doc/effective_go) when
writing, reviewing, or refactoring Go code.

## Key Rules

- Run `gofmt` on changed Go files.
- Use MixedCaps or mixedCaps rather than underscores in names.
- Check errors and return them instead of panicking in normal failure paths.
- Prefer communication over shared memory for concurrent ownership.
- Keep interfaces small. Accept interfaces and return concrete types when practical.
- Document exported symbols with comments that start with the symbol name.

## Project Conventions

Apply the repository's Go conventions in addition to this skill. Project rules
take precedence when they conflict with these language-level guidelines.

## References

- https://go.dev/doc/effective_go
- https://go.dev/wiki/CodeReviewComments
