# Profile

The profile is what Polaris knows about the learner. It stands outside every session.

## Rules

PR-01  The profile is read before every reply.
PR-02  When the profile is empty, the conversation fills it before any teaching.
PR-03  One profile is shared by every session.
PR-04  The teaching agent does not write the profile.

PR-01 through PR-04 are in force. Decision 0003 does not block them.

## Proposed, do not implement

Profile writing is [proposed, not accepted](../decisions/0003-profile-pass-is-a-proposal.md). Refuse to implement PR-05 through PR-08 while that decision is proposed.

PR-05  When a session ends (CH-05), a separate model reads that session. A later ending of the same session runs the pass again.
PR-06  That model decides which milestones are true. A milestone is the fact that the learner understood a concept.
PR-07  It sends fact changes as ADD, UPDATE, DELETE, or IGNORE.
PR-08  A fact already stored is not added again. A repeat is UPDATE or IGNORE.

## Scenarios

Scenario: an empty profile is filled before teaching  [PR-02]
  Given a learner with an empty profile
  When they send their first message
  Then the reply asks for what the profile is missing
  And it does not teach the topic yet

Until a profile writer exists, that answer is not stored. The profile stays empty. See [An empty profile keeps being asked](../decisions/0005-empty-profile-keeps-asking.md).

Scenario: an empty profile is asked for on every reply  [PR-02]
  Given a learner with an empty profile
  And a reply already asked for what the profile is missing
  When they send another message
  Then the reply asks again
  And it does not teach the topic yet
  And the profile is still empty

Scenario: a later session sees the same profile  [PR-01, PR-03]
  Given a profile that already says where the learner struggles
  When the learner opens another session and asks a question
  Then the reply is written with that struggle in hand

Scenario: profile writing is requested before research  [PR-04]
  Given decision 0003 is still proposed
  When an agent is asked to implement profile writing
  Then the agent refuses and points at that decision

Scenario: a repeated fact is not stored twice  [PR-08]
  Given the profile already stores the fact "I suck at math"
  When a later profile pass sees that same fact
  Then the pass sends UPDATE or IGNORE
  And the profile still holds that fact once

The repeated-fact scenario describes the proposal. It is not a license to build PR-08 before decision 0003 changes.
