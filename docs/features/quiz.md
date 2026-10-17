# Quiz

A quiz checks what the learner understood. It is an artifact of the session. The key of a question stays in the database until the learner checks that question. See [Answer key stays in the database](../decisions/0002-answer-key-stays-in-db.md), [Answer key shown after grading](../decisions/0007-answer-key-shown-after-grading.md), and [Answer key shown for each question as it is checked](../decisions/0009-answer-key-shown-per-question.md).

## Rules

QZ-01  A quiz starts in the chat turn that created it.
QZ-02  The learner can expand that same quiz onto its own page.
QZ-03  The browser never receives the key of a question before that question is checked. The key includes the correct choice, the explanation, and the wrong-choice notes.
QZ-04  Grading is done in code by comparing to the stored key, never by the model.
QZ-05  Each question has exactly one correct choice.
QZ-06  A checked question shows its feedback inside its choices. The correct choice is marked and shows the explanation of why it is right. A wrong pick is marked as the learner's answer and shows the wrong-choice note for it.
QZ-07  Creating a quiz stores it as an artifact of that session.
QZ-08  The score is kept with the quiz when its last question is checked.
QZ-09  The choices of each question are shuffled when the quiz is stored, so where the correct choice sits does not follow the model's habit.
QZ-10  A quiz is refused when a choice gives the answer away or depends on the choice order: a choice such as "all of the above" or "none of the above", a choice labelled with a letter, two choices with the same text, an explanation that names a choice by its letter, or a correct choice far longer than every other choice.
QZ-11  Every later reply in that session reads the score of each finished quiz, which questions were wrong, the choice the learner made, and for a wrong question the correct choice and the wrong-choice note for their choice.
QZ-12  Before a quiz is stored, a second model answers it without the key. If any answer differs from the key, or the check cannot finish, the quiz is not stored and the teaching agent is told why. The agent may send it once more in the same reply.
QZ-13  Each wrong choice has a wrong-choice note.
QZ-14  Picking a choice checks the question at once. A checked question is locked, and a second check on it is refused. A check that fails locks nothing and reveals nothing.
QZ-15  Each checked answer is stored with the quiz. A quiz that is opened again keeps its checked questions locked, with their feedback, and opens at the first question not yet checked.
QZ-16  When the last question is checked, its feedback stays on screen and the score and a list of every question marked right or wrong appear under it. A finished quiz opens on that results view, from where the learner can review every question with its feedback. In the chat, a finished quiz shows its score.

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

Scenario: code checks the pick  [QZ-04]
  Given a stored answer key
  When the learner picks a choice
  Then whether it is right is the comparison of that choice to the key
  And the model is not asked to grade

Scenario: one correct choice  [QZ-05]
  Given the agent created a quiz
  When the quiz is stored
  Then every question has exactly one correct choice in the key

Scenario: choices are shuffled  [QZ-09]
  Given the agent created a quiz whose correct choice is always first
  When the quiz is stored many times
  Then the correct choice is not always first

Scenario: a choice that gives the answer away is refused  [QZ-10]
  Given the agent created a quiz with the choice "All of the above"
  When the quiz is stored
  Then the quiz is refused
  And the agent is told which question to fix

Scenario: the next reply sees the score  [QZ-11]
  Given a quiz in the session whose last question the learner checked
  When the learner sends the next message
  Then the reply reads the score and which questions were wrong
  And a wrong question names the learner's choice, the correct choice, and the wrong-choice note

Scenario: a half-finished quiz is not read  [QZ-11]
  Given a quiz in the session with one question checked and one not
  When the learner sends the next message
  Then the reply does not read a score for that quiz

Scenario: checking shows the key of that question only  [QZ-03, QZ-06]
  Given a quiz with two questions
  When the learner picks a wrong choice on the first
  Then the first question returns the correct choice, its explanation, and the wrong-choice note for the pick
  And the second question has no key

Scenario: a right pick shows the explanation  [QZ-06]
  Given a quiz with two questions
  When the learner picks the correct choice on the first
  Then the first question returns its explanation and no wrong-choice note

Scenario: a checked question is locked  [QZ-14]
  Given a question the learner has checked
  When the learner picks a choice on it again
  Then the pick is refused
  And the stored answer is unchanged

Scenario: an invalid pick is refused  [QZ-14]
  Given a quiz
  When the learner picks a choice that is not on the question
  Then the pick is refused
  And the question is not checked

Scenario: the last check keeps the score  [QZ-08]
  Given a quiz with two questions, the first checked
  When the learner checks the second
  Then the score is kept with the quiz

Scenario: a reopened quiz keeps its answers  [QZ-15]
  Given a quiz with two questions, the first checked
  When the learner opens the quiz again
  Then the first question is locked and shows its feedback
  And the quiz opens at the second question

Scenario: the last check shows the results  [QZ-16]
  Given a quiz with two questions, the first checked
  When the learner checks the second
  Then the feedback of the second question stays on screen
  And the score and a right or wrong mark for each question appear under it

Scenario: a finished quiz opens on its results  [QZ-16]
  Given a finished quiz
  When the learner opens it from the tools panel
  Then the score and the marked list of questions show
  And the learner can review any question with its feedback

Scenario: a key the check disagrees with is refused  [QZ-12]
  Given the agent creates a quiz
  When a second model, without the key, picks another choice for a question
  Then the quiz is not stored
  And the agent is told which question disagreed

Scenario: a wrong choice needs a wrong-choice note  [QZ-13]
  Given the agent creates a quiz
  When a wrong choice has no wrong-choice note
  Then the quiz is not stored
