---
status: accepted
---

# Optional sign-in protects the profile

Polaris opens on the app. A learner who has not signed in can use chat, quiz, whiteboard, and animation. Sign-in is a button that opens the local sign-in page. It protects one thing: the profile and its evidence. Their endpoints refuse a request without a valid access token. Nothing else is gated.

An anonymous session reads no profile and runs no profile pass, so it does not ask for what the profile is missing. A turn is marked signed-in or anonymous when it is saved, and the profile pass reads only signed-in turns. A session that starts anonymous and signs in partway contributes only the turns after sign-in.

Sign-in uses two tokens. The access token lasts 60 minutes and lives only in page memory. The refresh token lasts 7 days and lives in an httpOnly, SameSite=Strict cookie scoped to the refresh path. The server stores only a hash of each refresh token. Each refresh issues a new refresh token, and reuse of an old one revokes the whole family. The signing key is made at first run and kept on the machine. The password is stored only as a salted hash.

Five wrong tries block sign-in for 10 minutes, even for the correct pair. The count is stored, so a restart does not reset it. The wrong-pair message does not say which part was wrong.

This replaces the part of [Local sign-in before Sunday](0004-local-sign-in-before-sunday.md) that made sign-in the gate to the whole app. The 18 Oct 2026 deadline in that decision still stands. Sign-in is still not the Claude login ([decision 0001](0001-personal-login-local-only.md)).

Reading earlier anonymous chats into the profile at sign-in was wanted and cut for time. It is parked in `later.md`.

[Anonymous sessions are not kept](0015-anonymous-sessions-are-not-kept.md) replaces the part of this decision that saved anonymous sessions.
