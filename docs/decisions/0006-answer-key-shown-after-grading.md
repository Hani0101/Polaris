---
status: accepted
---

# Answer key shown after grading

A missed question used to show its explanation but not the correct choice, because the browser never received the key (QZ-03). A graded quiz is locked: a second grade is refused. Once it is locked, the key gives nothing away.

So the browser receives the key with the graded quiz, and not before. Every question shows why its correct choice is right. A missed question also shows the correct choice and the wrong-choice note for the choice the learner made. Grading is still done in code against the stored key (QZ-04).

Before a quiz is stored, a second model answers it without the key (QZ-10). A key written by a model can be wrong, and code grading against a wrong key is confidently wrong. When the check disagrees or cannot finish, the quiz is not stored. The agent may fix it and send it once more in the same reply; after a second refusal it leaves the quiz out. Storing a quiz whose key was not checked was the alternative, and it was rejected.

See [the quiz research note](../research/0001-quiz-feedback.md).
