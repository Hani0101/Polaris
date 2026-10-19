# Auth

Sign-in is the local page the one learner can pass to be recognised by Polaris. It is optional. It is not the Claude login. See [Optional sign-in protects the profile](../decisions/0008-optional-sign-in-protects-the-profile.md), [Local sign-in before Sunday](../decisions/0004-local-sign-in-before-sunday.md), and [Personal login, local only](../decisions/0001-personal-login-local-only.md).

## Rules

AU-01  Polaris opens on the app. A learner who is not signed in can use chat, quiz, whiteboard, and animation.
AU-02  A Sign in button opens the sign-in page. The sign-in page exists by Sunday 18 Oct 2026.
AU-03  The sign-in stays on the machine. It is not Google OAuth, not an accounts server, and not the Claude login.
AU-04  The sign-in asks for a username and a password. There is one pair, for the one learner. The password is stored only as a salted hash.
AU-05  The first time the sign-in page is used, the learner chooses the pair. The password is entered twice, the username is not empty, and the password has at least 8 characters.
AU-06  After that, a matching pair signs the learner in. A mismatch leaves the learner on the sign-in page with a message that does not say which part was wrong.
AU-07  v1 has no way to replace a forgotten pair. There is no reset, no second pair, and no recovery screen.
AU-08  Signing in gives an access token that lasts 60 minutes. It is kept only in page memory and sent as a Bearer header.
AU-09  Signing in also gives a refresh token that lasts 7 days. It is a random value in an httpOnly, SameSite=Strict cookie scoped to the refresh path. The server stores only its hash. Each refresh issues a new refresh token and ends the old one. Reuse of an ended one revokes every refresh token from that sign-in.
AU-10  The page refreshes the access token without the learner doing anything. When the refresh token has expired or been revoked, the learner becomes anonymous, the page shows the signed-out state, and chat is not blocked.
AU-11  Signing out revokes the refresh token and clears the access token. It does not delete the profile.
AU-12  The profile and its evidence are reachable only with a valid access token. Without one the request is refused with 401. Everything else works without sign-in, except the learner's sessions (AU-16).
AU-13  Five wrong tries in a row block sign-in for 10 minutes, and the correct pair is refused during that time. The count is stored, so a restart does not reset it, and a successful sign-in resets it. The page says how long is left.
AU-14  Polaris answers only on this machine. A request from another address, or for a host name that is not this machine, is refused with 403. This covers every route, since most routes are open (AU-12) and the first use chooses the pair (AU-05).
AU-15  An anonymous session is not kept. It works while it is open, but it is not in the session list and cannot be reopened. When it ends (CH-05), it is removed with everything made in it, and no profile pass runs on it. See [decision 0015](../decisions/0015-anonymous-sessions-are-not-kept.md).
AU-16  A session started while signed in is the learner's. Without a valid access token the session list is empty, and opening, reading, or writing one of the learner's sessions, or a quiz or deck made in one, is refused with 404. The animation media, Manim assets, and resource files are the exception, since the page loads them by URL without a token.
AU-17  Signing in during an anonymous session keeps it: it becomes the learner's and is listed. Only its turns sent after sign-in reach the profile.
AU-18  Signing out, or becoming anonymous because the refresh token died (AU-10), takes the learner's sessions off the page and opens a new anonymous draft.

## Scenarios

Scenario: the app opens with no sign-in  [AU-01]
  Given the learner is not signed in
  When the learner opens Polaris
  Then the app opens
  And chat, quiz, whiteboard, and animation work

Scenario: the Sign in button opens the page  [AU-02]
  Given the app is open and the learner is not signed in
  When the learner presses Sign in
  Then the sign-in page is showing

Scenario: the page asks for a username and a password  [AU-04]
  Given the sign-in page is showing
  When the learner looks at it
  Then it asks for a username and a password
  And both are checked against the pair stored on the machine
  And the stored password is a salted hash, not the password

Scenario: the first visit chooses the pair  [AU-05]
  Given no pair is stored on the machine
  When the learner uses the sign-in page
  Then they choose the username and the password, entering the password twice
  And a password under 8 characters or an empty username is refused
  And that pair is stored on the machine

Scenario: a matching pair signs the learner in  [AU-06, AU-08, AU-09]
  Given a pair is already stored
  When the learner enters that pair
  Then the learner is signed in
  And the page holds a 60-minute access token in memory
  And a 7-day refresh token is set in an httpOnly cookie

Scenario: a mismatch stays on the page  [AU-06]
  Given a pair is already stored
  When the learner enters a username or password that does not match
  Then Polaris stays on the sign-in page
  And the message does not say whether the username or the password was wrong

Scenario: a forgotten pair cannot be replaced  [AU-07]
  Given a pair is already stored
  When the learner cannot remember it
  Then Polaris offers no reset, no second pair, and no recovery screen

Scenario: refreshing replaces the refresh token  [AU-09]
  Given the learner is signed in
  When the refresh token is used
  Then a new access token and a new refresh token are issued
  And the old refresh token no longer works

Scenario: reusing an ended refresh token revokes the sign-in  [AU-09]
  Given a refresh token that has already been replaced
  When it is used again
  Then every refresh token from that sign-in is revoked

Scenario: an expired access token is refreshed quietly  [AU-10]
  Given the learner is signed in and the access token has expired
  When the learner sends a message
  Then the page gets a new access token and the learner notices nothing

Scenario: a dead refresh token makes the learner anonymous  [AU-10]
  Given the refresh token has expired or been revoked
  When the page tries to refresh
  Then the page shows the signed-out state
  And the chat is not blocked
  And turns sent now are anonymous

Scenario: signing out ends the sign-in  [AU-11]
  Given the learner is signed in
  When they sign out
  Then the refresh token is revoked and the access token is cleared
  And the profile is still stored

Scenario: the profile is unreachable without a token  [AU-12]
  Given the learner is not signed in
  When a request asks for the profile or its evidence
  Then it is refused with 401
  And a request for chat, quiz, whiteboard, or animation still works

Scenario: five wrong tries lock sign-in for ten minutes  [AU-13]
  Given a pair is already stored
  When the learner enters a wrong pair five times in a row
  Then sign-in is blocked for 10 minutes
  And the correct pair is refused during that time
  And the page says how long is left

Scenario: a restart does not clear the lockout  [AU-13]
  Given sign-in is blocked
  When the server restarts
  Then sign-in is still blocked until the 10 minutes end

Scenario: a request from elsewhere is refused  [AU-14]
  Given Polaris is running on the learner's machine
  When a request comes from another machine, or names a host that is not this machine
  Then it is refused with 403
  And no pair can be chosen and no session can be read through it

Scenario: an anonymous session is not kept  [AU-15]
  Given the learner is not signed in
  When they send a message in a new session
  Then the session is not in the session list
  And when they leave it, it and its turns are removed
  And no profile pass runs on it
  And it cannot be opened again

Scenario: the learner's sessions are not shown when signed out  [AU-16, AU-18]
  Given the learner has a session from while they were signed in
  When they sign out
  Then the session list is empty and a new anonymous draft is open
  And a request to open or read that session is refused with 404

Scenario: signing in keeps the open session  [AU-17]
  Given the learner sent a message in an anonymous session
  When they sign in and send another
  Then the session is in the session list with both turns
  And the profile pass reads only the turn sent after sign-in

Scenario: sign-in is not the Claude login  [AU-03]
  Given the learner is on the sign-in page
  When they pass it
  Then the check stays on the machine
  And Google OAuth is not used
  And the Claude login is unchanged
