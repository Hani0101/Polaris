---
status: accepted
---

# The learner can edit the profile

Until now only the session-end pass wrote the profile ([decision 0003](0003-profile-pass-is-a-proposal.md)), and the learner could not see what it held. The learner can now see every fact in Settings, and add, reword, or remove one (PR-11). The next reply reads the profile as it stands (PR-01), so a change applies from the next message without a new session.

The teaching agent still does not write the profile (PR-04). The routes for learner edits need a valid access token (AU-12), and the agent cannot reach them, because it reads only public web pages (CH-26).

A learner edit is a fact with `written_by` set to `learner` and the basis `stated`. A rewording keeps the old wording as a retired fact that points to the new one, as a pass UPDATE does, so the evidence carries over. A removal retires the fact and records that the learner retired it. Nothing is deleted from the database.

A pass reads every signed-in turn of a session each time that session ends (PR-05). Without a guard, an old turn would put back a fact the learner had just removed. So code refuses a pass ADD or UPDATE whose text matches a fact the learner removed or reworded, unless a turn sent after that edit backs it (PR-12). The match uses the same wording rule as a repeat (PR-08). A paraphrase still gets through. Telling the pass model which facts the learner took out would close that gap, but it changes the pass prompt, which decision 0003 leaves to research.

A fact the learner adds is `unsorted`. Asking the learner to pick a kind was the alternative. It was left out because the agent reads only the text, and the pass can sort the fact later with an UPDATE.

The old idea of exposing the profile as an editable Markdown file was dropped in favor of this. Facts are rows with kinds, evidence, and history, and a file would lose them.
