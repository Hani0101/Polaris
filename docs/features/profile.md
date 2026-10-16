# Profile

The profile is what Polaris knows about the learner. It stands outside every session.

## Rules

PR-01  The profile is read before every reply.
PR-02  When the profile is empty, the conversation fills it before any teaching.
PR-03  One profile is shared by every session.
PR-04  The teaching agent does not write the profile.
PR-05  When a session ends (CH-05), a separate model reads that session. A later ending of the same session runs the pass again.
PR-06  That model decides which milestones are true. A milestone is the fact that the learner understood a concept.
PR-07  It sends fact changes as ADD, UPDATE, DELETE, or IGNORE.
PR-08  A fact already stored is not added again. A repeat is UPDATE or IGNORE.

PR-01 through PR-08 are in force. The pass design still needs research; see [decision 0003](../decisions/0003-profile-pass-is-a-proposal.md).

## Scenarios

Scenario: an empty profile is filled before teaching  [PR-02]
  Given a learner with an empty profile
  When they send their first message
  Then the reply asks for what the profile is missing
  And it does not teach the topic yet

The pass stores those answers when the session ends. Until then the profile stays empty. See [An empty profile keeps being asked](../decisions/0005-empty-profile-keeps-asking.md).

Scenario: an empty profile is asked for on every reply  [PR-02]
  Given a learner with an empty profile
  And a reply already asked for what the profile is missing
  When they send another message
  Then the reply asks again
  And it does not teach the topic yet
  And the profile is still empty

Scenario: leaving a session stores facts from it  [PR-05, PR-07]
  Given a session whose turns say how the learner wants to be taught
  When the learner leaves that session
  Then the profile stores those facts
  And a later session teaches with those facts in hand

Scenario: a later session sees the same profile  [PR-01, PR-03]
  Given a profile that already says where the learner struggles
  When the learner opens another session and asks a question
  Then the reply is written with that struggle in hand

Scenario: a repeated fact is not stored twice  [PR-08]
  Given the profile already stores the fact "I suck at math"
  When a later profile pass sees that same fact
  Then the pass sends UPDATE or IGNORE
  And the profile still holds that fact once

The pass design still needs research. Do not replace it without a research note that keeps this design or chooses another.
