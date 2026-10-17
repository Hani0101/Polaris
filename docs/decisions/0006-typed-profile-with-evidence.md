---
status: proposed
supersedes: 0003, 0005 (on acceptance)
---

# Typed profile with evidence

This record is proposed and is not in force. While it is proposed, [0003](0003-profile-pass-is-a-proposal.md) and [0005](0005-empty-profile-keeps-asking.md) stay accepted. The research behind it is [research note 0001](../research/0001-profile-design.md).

## What stays from 0003

- The teaching agent reads the profile and does not write it.
- The writer is a separate Haiku-class model.
- It runs when the learner leaves a session.
- It sends ADD, UPDATE, DELETE, or IGNORE.
- A repeated fact stays one stored fact.

## What changes from 0003

- **Store.** Each fact is a row in the session database. A row has a kind, text, a basis, and times. Its evidence rows point at the session, turn, quiz, or whiteboard behind it. `profile.json` is migrated once.

  The kinds are: goal, how they want to be taught, what they can do, where they struggle, and milestone.

  The basis says whether the learner stated the fact, a quiz or drawing showed it, or the pass inferred it.
- **Changes name a fact by id.** Code refuses an UPDATE, DELETE, or IGNORE that names no stored fact, and adds nothing in its place.
- **Inputs.** The pass reads only the turns it has not read before. With them, it reads the quizzes (choices, correct or not), whiteboards (the learner's drawing, comments, and pointing), and requests for a simpler drawing in those turns.
- **Milestones.** A milestone needs a graded quiz as evidence, and code checks it.
- **Failures.** A failed pass is recorded, the learner is told, and the pass is retried.
- **Learner control.** The learner can see, edit, remove, and add facts. The pass does not change a fact the learner wrote.

## What changes from 0005

While the profile is empty, the same pass also runs before each reply after the first. This is a checkpoint, and it reads the turns so far. If it stores facts, that reply teaches. If it stores nothing or fails, the reply asks again.

PR-02 and PR-04 both still hold:
- No reply teaches while the profile is empty.
- The teaching agent never writes the profile.

The 0005 rule that every reply asks for the whole first session is dropped.

## Rejected

- **Keeping the string list and only a longer prompt.** Matching by exact string can't handle reworded facts.
- **Tiered memory where the agent edits its own memory (MemGPT / Letta).** It breaks PR-04 and adds tool turns to every reply.
- **Teaching anyway in a first session.** This is rejected for the reason 0005 gives.
- **Full knowledge tracing now.** One learner gives too few graded answers per concept to fit it. It is kept as a later display beside milestones.

## Consequences

- PR-04 through PR-08 change wording, and PR-09 through PR-18 are added, as drafted in section 9 of the research note.
- The glossary gains Goal, Concept, Evidence, and Profile pass, and the Profile entry gains goal.
- When this is accepted:
  - 0003 and 0005 get `status: superseded by 0006`,
  - the line in CLAUDE.md that says the pass still needs research is removed.
- Quiz questions will later need a concept. That is a separate change to quiz.md.
