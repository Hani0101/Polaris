# Auth

Sign-in is the local page the one learner passes to open Polaris. It is not the Claude login. See [Local sign-in before Sunday](../decisions/0004-local-sign-in-before-sunday.md) and [Personal login, local only](../decisions/0001-personal-login-local-only.md).

## Rules

AU-01  Before Sunday 18 Oct 2026, and until the sign-in page exists, the app opens for the one learner with no sign-in.
AU-02  From Sunday 18 Oct 2026, Polaris opens on a sign-in page for that one learner.
AU-03  The sign-in stays on the machine. It is not Google OAuth, not an accounts server, and not the Claude login.
AU-04  The sign-in asks for a username and a password. Both are stored on the machine. There is one pair, for the one learner.
AU-05  The first time the sign-in page is used, the learner chooses the username and the password.
AU-06  After that, a matching pair opens Polaris. A mismatch leaves the learner on the sign-in page.
AU-07  v1 has no way to replace a forgotten pair. There is no reset, no second pair, and no recovery screen.

## Scenarios

Scenario: the app opens with no sign-in before the page exists  [AU-01]
  Given the sign-in page is not built
  And the date is before Sunday 18 Oct 2026
  When the learner opens Polaris
  Then the app opens with no sign-in

Scenario: Sunday opens on the sign-in page  [AU-02]
  Given the date is Sunday 18 Oct 2026 or later
  When the learner opens Polaris
  Then the first screen is the sign-in page

Scenario: the page asks for a username and a password  [AU-04]
  Given the sign-in page is showing
  When the learner looks at it
  Then it asks for a username and a password
  And both are checked against the pair stored on the machine

Scenario: the first visit chooses the pair  [AU-05]
  Given no pair is stored on the machine
  When the learner uses the sign-in page
  Then they choose the username and the password
  And that pair is stored on the machine

Scenario: a mismatch stays on the page  [AU-06]
  Given a pair is already stored
  When the learner enters a username or password that does not match
  Then Polaris stays on the sign-in page

Scenario: a forgotten pair cannot be replaced  [AU-07]
  Given a pair is already stored
  When the learner cannot remember it
  Then Polaris offers no reset, no second pair, and no recovery screen

Scenario: sign-in is not the Claude login  [AU-03]
  Given the learner is on the sign-in page
  When they pass it
  Then the check stays on the machine
  And Google OAuth is not used
  And the Claude login is unchanged
