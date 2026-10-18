# Polaris

Polaris teaches one learner through a conversation that can draw, animate, and check understanding.

## Language

**Learner**:
The person Polaris teaches.
_Avoid_: user, student, account

**Session**:
One conversation between the learner and the agent.
_Avoid_: thread, sign-in

**Draft**:
A new session that has no message yet. It is not in the session list, and it is discarded if the learner leaves it.
_Avoid_: empty session, pending session

**Session name**:
The label the learner gives a session. Without one, a session is labelled with its generated title, then with its first message.
_Avoid_: chat name, topic

**Generated title**:
A short title a cheap model writes once from a session's first message. The learner's session name wins over it.
_Avoid_: auto-name, summary

**Sign-in**:
The local page where the learner enters a username and a password so that Polaris keeps and uses their profile. It is optional.
_Avoid_: account, OAuth, Claude login, passphrase

**Anonymous session**:
A session held while the learner is not signed in. It reads no profile and adds nothing to it.
_Avoid_: guest, logged-out user

**Claude login**:
The login on the machine that Polaris uses to reach Claude.
_Avoid_: sign-in, API key

**Turn**:
One learner message and the agent reply that follows it. A session is those turns in order.
_Avoid_: message, prompt, exchange

**Profile**:
What Polaris knows about this learner, stored as facts: how they want to be taught, what they can already do, where they struggle, and the milestones they have reached.
_Avoid_: questionnaire, memory, user context, user skills, account

**Fact**:
One claim stored on the profile.
_Avoid_: note, memory, user context

**Milestone**:
A fact that the learner understood a concept.
_Avoid_: achievement, badge, progress

**Artifact**:
A whiteboard, quiz, animation, or flashcard deck kept so the learner can open it again.
_Avoid_: file, attachment, output

**Resource**:
Material the learner gives Polaris to explain from: a PDF, a Word document, a text file, a typed note, an image, or a web page added by its link. It belongs to one session. The agent reads it and never writes it.
_Avoid_: attachment, upload, file, source

**Web mode**:
A toggle in the chat input. Only a message sent with it on lets the agent search and read public web pages for that reply.
_Avoid_: browsing, internet mode, search mode

**Whiteboard**:
A drawing the agent and the learner use to explain an idea.
_Avoid_: canvas, diagram

**Quiz**:
A set of questions used to check what the learner understood.
_Avoid_: test, exam, questionnaire

**Checked question**:
A quiz question the learner has picked a choice for. Code compared the pick to the answer key, the question is locked, and its key is shown.
_Avoid_: submitted, graded question

**Finished quiz**:
A quiz whose last question has been checked. It has a score.
_Avoid_: graded quiz, completed quiz

**Wrong-choice note**:
A short sentence stored with a wrong choice on a quiz. It says why a learner might pick that choice and why it is wrong. It is part of the answer key.
_Avoid_: note, hint, distractor

**Flashcard**:
One concept for revision: a front, a back, and the source it comes from.
_Avoid_: note, question, card (alone)

**Deck**:
The set of flashcards the agent made in one turn. It is an artifact.
_Avoid_: set, collection, stack

**Rating**:
The learner's mark on a flashcard after flipping it: got it or again. It stays with the deck and never reaches the profile.
_Avoid_: score, grade, mastery

**Appearance mode**:
The learner's choice of System, Light, or Dark colors. It is kept in the browser, not on the profile.
_Avoid_: theme, skin, dark mode (as the name of the setting)

**Animation**:
A moving explanation the learner can watch.
_Avoid_: illustration, video

**Job**:
A request that takes long enough that the learner can keep talking, and is told when it has finished. In v1, a job produces an animation.
_Avoid_: task, render, worker

**Notice**:
An operating-system notification that a job has finished.
_Avoid_: toast, badge, in-app message
