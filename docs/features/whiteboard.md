# Whiteboard

A whiteboard is a drawing the agent and the learner work on together. It is an artifact of the session.

## Rules

WB-01  The agent can draw on the whiteboard.
WB-02  The learner can draw on the whiteboard and leave a comment.
WB-03  A later turn in the session can see the learner's drawing and comment.
WB-04  Creating a whiteboard stores it as an artifact of that session. The learner can open it again from the session.
WB-05  The backend checks the drawing data before the browser draws it.

## Scenarios

Scenario: the agent draws  [WB-01]
  Given a session
  When the agent decides a drawing will help
  Then the whiteboard shows the agent's drawing

Scenario: a learner comment survives  [WB-02, WB-03]
  Given a whiteboard in the session
  When the learner draws on it and leaves a comment
  Then a later turn in that session still shows that drawing and that comment

Scenario: bad drawing data is refused  [WB-05]
  Given the agent produced drawing data
  When the data fails the check
  Then the browser does not draw it
