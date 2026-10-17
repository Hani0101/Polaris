---
status: accepted
---

# Answer key shown for each question as it is checked

[Decision 0007](0007-answer-key-shown-after-grading.md) showed the key only once the whole quiz was graded. The learner picked every answer, pressed "Check answers" on the last question, and only then saw why any of them was right or wrong. By then they had forgotten what they were thinking.

So a question is checked the moment the learner picks a choice. Code compares the pick to the stored key (QZ-04) and the browser receives that question's key: the correct choice, the explanation, and the wrong-choice note for the choice made. The keys of questions not yet checked stay in the database (QZ-03).

A checked question is locked, as a graded quiz was before. A second check on it is refused, so showing its key gives nothing away. A pick that fails to reach the server locks and reveals nothing.

Each checked answer is stored with the quiz, so a reload keeps it. The quiz is finished when its last question is checked. Only then is the score computed and kept (QZ-08), and only a finished quiz reaches later replies (QZ-11). A half-finished quiz is not yet a result worth teaching from.

Picking a choice and checking it are one action. A misclick locks a wrong answer. That cost was accepted so the feedback is immediate and the learner needs no extra button.

Amends [decision 0007](0007-answer-key-shown-after-grading.md) and [decision 0002](0002-answer-key-stays-in-db.md): the key of a question stays in the database until that question is checked, not until the quiz is graded.
