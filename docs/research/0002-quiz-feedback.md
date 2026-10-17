---
status: proposed
---

# Quiz evidence and feedback

Findings about what a quiz does after the learner submits it. Each finding has a proposal and names the rules and decisions it would change. Nothing here is in force until it is accepted.

Accepted: finding 1's teaching side (QZ-11), finding 2 (QZ-12), finding 3 (QZ-03, QZ-06, [decision 0007](../decisions/0007-answer-key-shown-after-grading.md)), and finding 5 (QZ-13). With finding 3, a right answer also shows its explanation. Finding 4 and the profile side of finding 1 are still proposals.

## 1. Quiz results go nowhere

Before QZ-11, the next reply never saw the score. The profile pass reads only the text of each turn (`session_prompt` in `api/polaris/profile_pass.py`). So the pass decides milestones (PR-06) without the quiz evidence.

- Teaching side: done. QZ-11 gives every later reply in the session the score, the wrong questions, and the learner's choice for each one.
- Profile side: open. Feeding quiz results to the pass changes how the pass reads a session, so it needs research first, per [decision 0003](../decisions/0003-profile-pass-is-a-proposal.md). The research should ask whether a graded quiz is enough to set a milestone, and whether a missed question should lower one already stored.

## 2. The answer key is never checked

QZ-04 grades in code against the stored key. Nothing checks that the key is right. In one medical-education study, about 22% of quiz questions written by ChatGPT had factual or conceptual errors (source to be added). Grading in code against a wrong key is confidently wrong.

Proposal: before a quiz is stored, a cheap second model, in the class of Haiku, answers it without the key. If any of its choices differ from the key, the quiz is refused and the teaching agent is told which questions disagreed, as with any invalid quiz.

Would add a quiz rule. QZ-04 stays: the model still does not grade the learner. Cost: one more model call each time a quiz is created.

## 3. The correct choice is hidden after a miss

QZ-03 is applied to the whole quiz, at every point in its life. A missed question shows its explanation (QZ-06) but not the correct choice. A graded quiz is locked: a second grade is refused. Once it is locked, showing its key gives nothing away.

Proposal: QZ-03 becomes "The browser never receives the answer key before the quiz is graded." After grading, each missed question shows its correct choice.

Would change QZ-03, its scenario, QZ-11's last sentence, the teaching prompt's "never put the correct choices in the reply text", the security line in [product](../product.md), and [decision 0002](../decisions/0002-answer-key-stays-in-db.md).

## 4. Confidence ratings

Asking "how sure are you?" for each question helps. Answers given with high confidence that turn out wrong are corrected more often after feedback than wrong answers given with low confidence (the hypercorrection effect; Butterfield and Metcalfe, 2001). A rating also catches a lucky guess: a right answer marked as a guess still gets its explanation.

Proposal: each question takes a confidence (sure, unsure, guessing) with the choice. It is stored with the submission. QZ-06 explains wrong answers and right answers marked as guessing. QZ-11 also gives the next reply each confidence, so a sure but wrong answer is taught first.

Would change QZ-06 and QZ-11, the grade request, and the stored submission.

## 5. Feedback for each wrong choice

Today one explanation covers a question, whichever wrong choice the learner made. Diagnostic questions, such as Eedi's, store a short note for each wrong choice that names the misconception behind it.

Proposal: each wrong choice carries a wrong-choice note on why it is wrong. After grading, a missed question shows the wrong-choice note for the choice the learner made, then the explanation. The wrong-choice note is part of the key until grading, so QZ-03 covers it.

Would change QZ-06 and the quiz the agent creates (`create_quiz` input and `normalize_spec`).

## 6. Later

Parked in [later](../../later.md):

- A numeric answer graded within a tolerance. Would change QZ-05, which allows only choices.
- Retrying a missed question until it is right.
- Bringing missed questions back in later sessions with spaced repetition, for example the `fsrs` package.
