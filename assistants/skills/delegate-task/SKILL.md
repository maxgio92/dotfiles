---
name: delegate-task
description: "Use when a command, Workflow, or orchestrating session hands work to a specialist agent: picking the agent, writing the packet it receives, reading its reply, and relaying the result. Use for any Agent-tool launch, Workflow agent() prompt, or subagent hand-off, even when the user only says 'delegate', 'launch an agent', 'ask peter', or 'have dastardly review this'."
---

# Delegate Task

One contract for every hand-off: which specialist, what it receives, what it sends back, and how the result reaches the user.

## Agents

- `blast`: security auditor; sweeps a scope for exploitable paths, cites a CWE or OWASP class per finding.
- `brain`: test engineer; suggests high-impact unit tests that follow existing patterns.
- `dastardly`: adversarial code reviewer; challenges design, verifies trust boundaries, reports evidence-backed findings.
- `dexter`: Nix, Nixpkgs, NixOS, Home Manager, and nix-darwin specialist; packages and flakes.
- `donatello`: implementation engineer; executes code changes from a plan, keeps style.
- `edison`: conference presentation builder; adapts to talk format, depth, and style.
- `garfield`: git workflow assistant; Conventional Commits messages and pull request text.
- `gonzales`: performance specialist; high-impact optimisations in bottlenecks.
- `openscad-agent`: OpenSCAD pipeline; versioned `.scad` files, previews, validated STL exports.
- `pat`: blog posts and long-form technical articles in Massimiliano's voice.
- `penry`: maintainability reviewer; small, safe simplification, deduplication, and naming clarity.
- `pepe`: LOVE 2D and Lua 5.1 game development expert.
- `peter`: implementation engineer; smallest correct change, cross-system checks, build, test, lint gates.
- `rosey`: prompt and skill specialist; agents, skills, commands, and instruction files.
- `snagglepuss`: naming specialist; descriptive, consistent identifiers within project conventions.
- `velma`: documentation specialist; concise, verified docs organised by reader intent.

## Route

- Implementation from a task or a prompt: `peter`. Executing an existing improvement plan step by step: `donatello`.
- Adversarial diff review: `dastardly`. Security sweep of a scope: `blast`.
- Tests: `brain`. Documentation: `velma`. Naming: `snagglepuss`. Maintainability: `penry`. Performance: `gonzales`.
- Nix: `dexter`. Prompts, skills, commands, instruction files: `rosey`.
- Git messages: `garfield`. Blog: `pat`. Talks: `edison`. LOVE 2D: `pepe`. 3D printing: `openscad-agent`.
- No match: the smallest capable specialist, or ask the user.

Pick from the descriptions; the specialist does its own discovery.

## Depth

Workers never launch agents. A user-invoked command or Workflow is the sole orchestrator. A worker that needs another specialist returns early and describes the follow-up; the orchestrator routes it.

## Context

Fresh by default. Fork only when the parent transcript is essential. The middle path is a 200 to 500 word briefing (goal, decisions, constraints and paths, open questions, suggested skills) in the packet's Context field; the worker still starts fresh.

## Packet

Fields in this order; omit any that do not apply:

```
Task: <outcome required>
Context: <decisions, constraints, paths, risks, user preferences>
Authority: <external mutations permitted; restate them, fresh context inherits no consent>
Scope: <files, commands, sources, behaviours; what is out of scope>
Deadline: <hard stop in prose>
Validation: <checks to run or evidence to return>
Output: <report or artefact; format; file path if any; length budget for the reply>
Discipline: No preamble. Do not restate the task. Reply in text. Omit empty sections.
            The communication-rules hook scans your prose; write to pass it.
```

Keep a review packet to three or four named targets; a long multi-target packet is the observed cause of workers stalling and returning nothing.

## Response contract

The reply is the deliverable; a reply without the result is a failed task, whatever else the worker did. "My area is clean" is a complete, valid reply. Non-artefact work starts with `Answer:` unless the packet's Output field or a caller schema fixes another format; a pure artefact returns only the artefact. Section order when present: Answer, Recommendations, Evidence, Files, Changes, Tests, Blockers, Artefact.

## Re-request and fallback

When a worker returns empty, re-request once: a one-line recap of its scope, the two or three questions that matter most, and an instruction to reply in text. A second failure is the orchestrator's own work, to the same standard.

A worker may also write a named fallback file under the `review-reports` convention; the file is never reused and never the primary channel.

## Relay

- Artefact (commit message, PR body, drafted comment, generated code, file content): relay verbatim. `Observations:` may follow only for safety; it never replaces the artefact.
- Report (findings, research, review, status): deliver as answer plus recommendations, keeping every fact the user must act on.
- Long report: the worker writes it under `review-reports` and returns conclusion plus path; relay both.
