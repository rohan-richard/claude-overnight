---
description: Check the overnight queue, limits, and any finished results
allowed-tools: Bash(overnight status:*), Bash(overnight list:*), Bash(overnight results:*)
---

Check on the overnight batch:

- Run `overnight status` for the current window/limits and whether a batch
  would run right now.
- Run `overnight list` to see pending/done/failed jobs.
- If there are done jobs, run `overnight results` for the digest. Mention
  `overnight results <id>` to read one report, or `overnight resume <id>` /
  `/followup <id> ...` to continue a job's session.

Summarize what's pending, what finished, and anything that failed and why.
