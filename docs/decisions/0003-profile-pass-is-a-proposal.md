---
status: accepted
---

# Profile pass

Accepted so the session-end writer can run. The design still needs research: it has not been compared with alternatives. A later research note may keep this pass or replace it.

The teaching agent reads the profile and does not write it. The writer is a separate model, in the class of Haiku, because the job is simple reading of the session. It runs when the learner leaves the session, including when they switch to another session. It decides which milestones are true, and sends fact changes as ADD, UPDATE, DELETE, or IGNORE. A repeated fact, such as "I suck at math", stays one stored fact.
