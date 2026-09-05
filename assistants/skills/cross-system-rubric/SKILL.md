---
name: cross-system-rubric
description: Use when writing or reviewing code where data crosses a system boundary - parsers for CI logs, webhooks, API payloads, or model output; values sent to another system; invariants with multiple writers; consumers of changed result types; or code gated by build tags, Cargo features, or CI matrix variants. Provides the checks an implementer must apply and a reviewer must verify, including the build-flavor gate.
---

# Cross-System Rubric

Checks for data that enters from or leaves for another system. Implementers apply them before shipping; reviewers verify them and grade failures.

## The checks

1. **Ground the format.** Base any parser on a captured sanitised artefact or an authoritative schema, documentation page, or producer implementation. An invented fixture alone is insufficient. Record stable provenance in the fixture or test comment when it helps future maintainers. If no authoritative source is accessible, state the assumption explicitly and keep the parser fail-closed.
2. **Trace authority.** Identify who can influence each parsed value. Untrusted text may propose a value, but must not independently authorise a write target or policy decision. Corroborate it against trusted state and restrict it to an owned set such as compiled configuration or an allowlist. Check traversal only when parsed data reaches a path operation.
3. **Use consumer semantics.** Validate values against the destination system's documented grammar and comparison rules, confirmed through source, authoritative documentation, or a focused experiment. Test equality, minimum, maximum, quoting, and alternate numeric forms only when the contract admits them; reject representations the consumer cannot parse.
4. **Cover every writer.** Enumerate every reachable path that can update the invariant: fast, model, retry, and iterative paths. Enforce it at a shared choke point where possible. Test both directions of ordered change plus every representation the system actually produces. After changing a guard or parser, rerun the relevant cases for every supported representation, not only the one that exposed the bug.
5. **Verify cardinality.** Do not assume one record or candidate unless a trusted contract guarantees it. Without that guarantee, implement and test aggregation, duplicates, and remainder handling before optimising the singular case. Not every singular assumption is wrong; verify the contract first.
6. **Keep selected data coherent.** Return the selected identity with its data and derive dependent fields (paths, render fields) from that same selection. Read consumers of a changed result type so zero values and omitted fields do not silently break their contract.

## Build flavors

Enumerate every build flavor before declaring the build green: Go build tags (`grep -rn '//go:build'` over the affected tree), Cargo features and cfg-gated code, and any CI matrix variant that compiles the touched files. Build each flavor a CI job builds. A default build passing proves nothing about a file a tag or feature excludes from it.

A flavor that cannot compile locally (missing toolchain or system library) is a BLOCKED gate, not a passed one: stop and surface it as unverified. Grep or by-inspection evidence does not substitute for compilation.

## Reviewer severity

- Treat a reachable wrong behaviour under checks 1-6 as `block`, but establish reachability and the violated contract first.
- When no authoritative source is accessible, require an explicit assumption and fail-closed behaviour rather than inventing a production mismatch.
- Block skipped or build-tagged coverage only when the changed behaviour depends on it and CI does not run it. Read the relevant CI workflow before claiming a tagged test does or does not run.
