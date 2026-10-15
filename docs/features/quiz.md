# Quiz

A quiz checks what the learner understood. It is an artifact of the session. The answer key stays in the database. See [Answer key stays in the database](../decisions/0002-answer-key-stays-in-db.md).

## Rules

QZ-01  A quiz starts in the chat turn that created it.
QZ-02  The learner can expand that same quiz onto its own page.
QZ-03  The browser never receives the answer key.
QZ-04  Grading is done in code by comparing to the stored key, never by the model.
QZ-05  Each question has exactly one correct choice.
QZ-06  After grading, the learner is told which questions were wrong, and those mistakes are explained.
QZ-07  Creating a quiz stores it as an artifact of that session.
QZ-08  The score is kept with the quiz.

## Scenarios

Scenario: quiz payload has no answers  [QZ-03]
  Given the agent created a quiz
  When the frontend receives the quiz event
  Then no question contains an "answer" or "correct" field

Scenario: the learner expands the quiz  [QZ-01, QZ-02]
  Given a quiz shown in the chat
  When the learner expands it
  Then the same quiz is on its own page

Scenario: code grades the quiz  [QZ-04]
  Given a stored answer key
  When the learner submits choices
  Then the score is the comparison of those choices to the key
  And the model is not asked to grade

Scenario: one correct choice  [QZ-05]
  Given the agent created a quiz
  When the quiz is stored
  Then every question has exactly one correct choice in the key
