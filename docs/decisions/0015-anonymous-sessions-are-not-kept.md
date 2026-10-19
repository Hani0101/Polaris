---
status: accepted
---

# Anonymous sessions are not kept

[Optional sign-in protects the profile](0008-optional-sign-in-protects-the-profile.md) gated only the profile. Every session was saved and listed for whoever opened Polaris, so a learner who signed out still saw the chats they had while signed in. Sign-in now also protects the learner's sessions.

A session is the signed-in learner's from the moment it is started while signed in, or from the moment the learner signs in during it. A request without a valid access token does not see those sessions. The list is empty for it, and opening or reading one of them is refused as if the session were not there (404). Saying "not there" rather than 401 does not reveal that a session exists.

An anonymous session still works while it is open: chat, quiz, whiteboard, animation, and resources (AU-01). It is never listed, and it cannot be reopened. When it ends (CH-05), it is removed with everything made in it, as a delete removes it (CH-12), and no profile pass runs on it. Anonymous sessions that ended before Polaris stopped are removed when it starts again.

Signing in during an anonymous session keeps it: it becomes the learner's and is listed. As decision 0008 says, only the turns after sign-in reach the profile. The session records when it became the learner's, and the pass reads only turns from then on.

Signing out, or a sign-in that runs out (AU-10), takes the learner's sessions off the page and opens a new anonymous draft.

Sessions saved before this decision are treated as the learner's, so none of them is lost. Anonymous sessions from that time are indistinguishable from signed-in ones and are kept with them.

The animation media, Manim assets, and resource files are loaded by URL, so the page sends no access token with them. Those routes keep working by their unguessable ids and do not check the sign-in. Every other route of a session, and the quiz and deck routes, does.

This replaces the part of decision 0008 that saved anonymous sessions and marked each turn signed-in or anonymous. Its rule that only signed-in turns reach the profile stands.
