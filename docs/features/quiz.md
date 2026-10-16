# Quiz

A quiz checks what the learner understood. It is an artifact of the session. The answer key stays in the database until the quiz is graded. See [Answer key stays in the database](../decisions/0002-answer-key-stays-in-db.md) and [Answer key shown after grading](../decisions/0006-answer-key-shown-after-grading.md).

## Rules

QZ-01  A quiz starts in the chat turn that created it.
QZ-02  The learner can expand that same quiz onto its own page.
QZ-03  The browser never receives the answer key before the quiz is graded. The key includes the correct choice, the explanation, and the wrong-choice notes.
QZ-04  Grading is done in code by comparing to the stored key, never by the model.
QZ-05  Each question has exactly one correct choice.
QZ-06  After grading, every question shows its explanation of why the correct choice is right. A wrong question also shows the correct choice and the wrong-choice note for the choice the learner made.
QZ-07  Creating a quiz stores it as an artifact of that session.
QZ-08  The score is kept with the quiz.
QZ-09  Every later reply in that session reads the score of each graded quiz, which questions were wrong, the choice the learner made, and for a wrong question the correct choice and the wrong-choice note for their choice.
QZ-10  Before a quiz is stored, a second model answers it without the key. If any answer differs from the key, or the check cannot finish, the quiz is not stored and the teaching agent is told why. The agent may send it once more in the same reply.
QZ-11  Each wrong choice has a wrong-choice note.

## Scenarios

Scenario: quiz payload has no answers  [QZ-03]
  Given the agent created a quiz
  When the frontend receives the quiz event
  Then no question contains an "answer" or "correct" field
  And no choice contains a wrong-choice note

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

Scenario: the next reply sees the score  [QZ-09]
  Given a quiz in the session that the learner submitted
  When the learner sends the next message
  Then the reply reads the score and which questions were wrong
  And a wrong question names the learner's choice, the correct choice, and the wrong-choice note

Scenario: grading shows the key  [QZ-03, QZ-06]
  Given a quiz the learner submitted with one question right and one wrong
  When the graded quiz is returned
  Then the right question shows its explanation
  And the wrong question shows the correct choice, the wrong-choice note for the learner's choice, and the explanation

Scenario: a key the check disagrees with is refused  [QZ-10]
  Given the agent creates a quiz
  When a second model, without the key, picks another choice for a question
  Then the quiz is not stored
  And the agent is told which question disagreed

Scenario: a wrong choice needs a wrong-choice note  [QZ-11]
  Given the agent creates a quiz
  When a wrong choice has no wrong-choice note
  Then the quiz is not stored
