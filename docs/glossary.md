# Polaris

Polaris teaches one learner through a conversation that can draw, animate, and check understanding.

## Language

**Learner**:
The person Polaris teaches.
_Avoid_: user, student, account

**Session**:
One conversation between the learner and the agent.
_Avoid_: thread, sign-in

**Sign-in**:
The local page where the learner enters a username and a password to open Polaris.
_Avoid_: account, OAuth, Claude login, passphrase

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
A whiteboard, quiz, or animation kept so the learner can open it again.
_Avoid_: file, attachment, output

**Whiteboard**:
A drawing the agent and the learner use to explain an idea.
_Avoid_: canvas, diagram

**Quiz**:
A set of questions used to check what the learner understood.
_Avoid_: test, exam, questionnaire

**Wrong-choice note**:
A short sentence stored with a wrong choice on a quiz. It says why a learner might pick that choice and why it is wrong. It is part of the answer key.
_Avoid_: note, hint, distractor

**Animation**:
A moving explanation the learner can watch.
_Avoid_: illustration, video

**Job**:
A request that takes long enough that the learner can keep talking, and is told when it has finished. In v1, a job produces an animation.
_Avoid_: task, render, worker

**Notice**:
An operating-system notification that a job has finished.
_Avoid_: toast, badge, in-app message
