---
description: Queue a follow-up on a previous overnight job's session
allowed-tools: Bash(overnight followup:*), Bash(overnight list:*)
---

Queue a follow-up for an existing overnight job. The user's request is:
$ARGUMENTS

- It should start with a job id (or an unambiguous fragment of one), followed
  by the follow-up question. If no id is given, run `overnight list` and ask
  which job to follow up on.
- Run `overnight followup <id> "<question>"`.
- If it errors because the job has no saved session, tell the user and
  suggest `/queue` for a fresh question instead.

Confirm it was queued and mention it will resume that job's session in the
next overnight window.
