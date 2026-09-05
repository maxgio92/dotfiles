---
name: review-reports
description: "Where review and audit reports live: durable per-user storage with slugged, parallel-safe file names. Use whenever an agent writes a review, audit, security, or analysis report to disk, or asks where a report should go."
---

# Review Reports

Write reports to durable per-user storage, never into the repository under
review:

```
~/reports/<repo>/<YYYY-MM-DD>-<agent>-<slug>.md
```

- `<repo>`: the repository directory name (e.g. `dotfiles`, `mono`).
- `<agent>`: who produced it (`blast`, `dastardly`, `penry`, ...).
- `<slug>`: two to four kebab-case words naming the scope
  (e.g. `webhook-auth-audit`).

Create the directory if missing. Two runs on the same day get distinct slugs;
append `-2` only on a true collision. Start every report with the scope, the
commit sha reviewed, and the date, so the file stands alone. Reports are
read-only history: append a dated follow-up section instead of rewriting past
findings.
