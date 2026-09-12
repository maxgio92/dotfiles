---
name: sizing
description: "Use when estimating or sizing a task: assigning a T-shirt size (XS, S, M, L, XL), filling an estimate field in Linear or GitHub, or filling a Complexity field in a plan or handover. Use whenever the user mentions estimating, sizing, story points, or asks how big a piece of work is."
source: https://github.com/wimpysworld/nix-config/blob/main/home-manager/_mixins/agentic/assistants/skills/sizing/SKILL.md
---

# Sizing

One definition of the T-shirt scale. Size on what the work looks like, never on how long it might take.

## The scale

| Size | Points | What it looks like |
| ---- | ------ | ------------------ |
| XS | 1 | Trivial and self-evident. A config change, a docs fix, a small bug fix, a single-file edit. No design decision. |
| S | 2 | One focused slice, fully bounded. A standalone bug fix or feature slice with its own tests. Stays inside one module. |
| M | 3 | The workhorse. Clear scope, one owner, several files in one subsystem, with tests and docs. |
| L | 5 | The largest single unit. A new component, or a cross-cutting interface change with a settled design. |
| XL | 8 | The whole of a small feature. See the XL rule below. |

## Rules

- Index on what the work looks like, never on elapsed time. Do not estimate in days or weeks.
- Unresolved design is not a size, it is a spike. File the spike at XS or S, then size the real work once the design is settled.
- Parent tracking issues carry no estimate. The children carry the size.
- Work stops at L. XL is for personal repositories only, never on the `FUL` team, and splitting into a parent plus children is still the better move.
- Confirm the scale against the live workspace before assigning.


## Sprint loading

A human sanity check, not an agent input. A two-week sprint holds 8 XS, or 4 S, or 2 M, or 1 L.
