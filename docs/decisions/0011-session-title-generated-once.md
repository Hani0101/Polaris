---
status: accepted
---

# Session title is generated once

A new session is a draft and joins the session list on its first send. The draft is a hidden row, because resources and the agent warm-up need a session id before the first message. Leaving it deletes the row, with its resources, instead of ending it. A separate model, in the class of Haiku, writes a short title from that first message only, once per session. It sees no resources, profile, or reply, so it is cheap and keeps profile data out. It runs off the request path, so the reply never waits for it.

The learner can still rename the session. Their name wins over the generated title, and a late title never replaces it. A failed title is silent and the first-message label stays, because a title is cosmetic and a retry would break "once".
