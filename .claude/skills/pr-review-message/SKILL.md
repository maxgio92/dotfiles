---
name: pr-review-message
description: Draft replies to pull request review comments in Massimiliano's voice. Use for any reply on a PR thread: confirming and reporting a fix, agreeing with a suggestion, pushing back, or closing out a review round. The register differs from Slack posts and documentation, so reach for this instead of defaulting to either of those.
---

# pr-review-message

Review replies are short, factual, and settle the thread. Lead with the
verdict, then the substance. Reply in the thread the comment lives in, one
reply per finding, and reply to every finding: addressed or not.

## Reporting a fix

Open with the verdict and the commit: `fixed in <sha>.`, or `Valid: fixed in
<sha>.` when confirming the finding first. Then state what the code does now,
in plain declarative sentences: behavior, not effort. Name anything
intentionally left as is, with the reason.

```
Valid: fixed in ab12cd3ef4. Comment lines are now skipped, with a test pinning
the commented case. The echoed form stays an accepted false positive: telling
it apart needs a full lexer, and that failure direction is a miss the
downstream check still catches.
```

When one commit fixes several findings, address the reviewer, count them, and
number the answers in the order the findings were raised:

```
@reviewer all three confirmed and fixed in ab12cd3ef4.

1. Matching: the parser lowercases the reported name, so mixed-case
   duplicates dedupe.
2. Hard gate: parse errors now fail the run instead of logging.
3. Default: the flag is declared required with no default.
```

## Agreeing

State the agreement, then the reason in one sentence. Scope what this PR
covers against what the agreement implies for later work; a forward-looking
suggestion can close the reply.

```
Agreed. Splitting per type makes sense given how much the tool needs to get
these right. This PR only covers the native case, so we can treat it as one
slice to fold into that structure.
```

## Pushing back or deferring

Conclusion plus one reason, two sentences at most. On another team's project,
frame the point as a question and defer to the maintainers. Open minor,
optional points with `Just a detail (non-blocking):`. Out-of-scope but real
concerns get named and pointed at a tracking issue.

## Register

Kind and concise from the first draft; adversarial verification detail stays
internal. Plain prose: no bold, no headers, no bullet lists outside the
numbered multi-finding form. Reference commits by sha. Own an accepted
limitation plainly instead of papering over it. The personal writing standards
apply (no em dashes, no puffery, no LLM tells).
