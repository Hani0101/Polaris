# Chat

A session is the conversation. A turn is one typed message and the reply that follows it.

## Rules

CH-01  The learner's side of a turn is a typed message.
CH-02  The reply can include text and any artifacts created in that turn: a whiteboard, a quiz, or an animation job.
CH-03  The learner sees the reply as it is produced.
CH-04  The learner can start a new session and reopen an earlier one.
CH-05  A session ends when the learner leaves it, including when they switch to another session.

Profile rules PR-01, PR-02, and PR-03 apply before a teaching reply. While an animation job runs, AN-02 and AN-03 apply in the chat.

## Scenarios

Scenario: a turn carries an artifact  [CH-02]
  Given a session whose profile is already filled
  When the learner asks for an explanation that needs a drawing
  Then the reply includes the text and a whiteboard artifact

Scenario: an earlier session can be reopened  [CH-04]
  Given the learner has an existing session
  When they open that session again
  Then its turns are still there

Scenario: switching sessions ends the one they left  [CH-05]
  Given the learner is in a session
  When they switch to another session
  Then the session they left has ended

Scenario: the reply appears while it is still being produced  [CH-03]
  Given the learner has sent a message
  When the agent is still producing the reply
  Then the learner can see the part of the reply already produced
