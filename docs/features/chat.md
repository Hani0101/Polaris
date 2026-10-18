# Chat

A session is the conversation. A turn is one typed message and the reply that follows it.

## Rules

CH-01  The learner's side of a turn is a typed message. Resources the learner adds to the session are not part of a turn (RS-17).
CH-02  The reply can include text and any artifacts created in that turn: a whiteboard, a quiz, or an animation job.
CH-03  The learner sees the reply as it is produced.
CH-04  The learner can start a new session and reopen an earlier one.
CH-05  A session ends when the learner leaves it, including when they switch to another session.
CH-06  The learner can give a session a name, and change it later, from the session list. A session without a name is labelled with its first message.
CH-07  A name is trimmed and at most 80 characters. A blank name removes it.
CH-08  Naming a session changes its label only. It does not open or end the session, add a turn, or stop a reply in progress. The agent and the profile pass never read it.
CH-09  The reply text is drawn from a small Markdown subset: headings, numbered and bulleted lists, paragraphs, bold, key terms (`==term==`), struck text (`~~text~~`), inline code, code blocks with syntax colors when they name a language, tables, quotes, callouts (`> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`), maths (`$...$` and `$$...$$`), and web links. Anything else is shown as plain text, and italic is never shown.
CH-10  Raw HTML in a reply is shown as text and never rendered. Only http and https links become links. Maths that cannot be read is shown as its source.
CH-11  The learner can delete a session from its row in the session list, after one confirmation. The confirmation names the session, says it cannot be undone, and says the profile keeps what it learned.
CH-12  Deleting removes the session, its turns, its resources (RS-18), and the whiteboards, quizzes, and animation jobs made in it. Nothing is archived and there is no undo. The profile is not changed by the delete.
CH-13  The learner can delete the session they have open. It ends first (CH-05), and then a new empty session opens.
CH-14  A reply or animation job still running in the session is stopped before it is deleted. A write that arrives for a deleted session, including a resource upload, is dropped.
CH-15  A learner can delete only their own sessions. An anonymous session can be deleted too.
CH-16  In a signed-in session, deleting waits for the profile pass on it to finish (PR-05). If the pass fails, the session is still deleted and the learner is told that its facts were not saved.
CH-17  Opening a session that no longer exists tells the learner so and opens a new empty session.

Profile rules PR-01, PR-02, and PR-03 apply before a teaching reply. While an animation job runs, AN-02 and AN-03 apply in the chat.

## Scenarios

Scenario: a turn carries an artifact  [CH-02]
  Given a session whose profile is already filled
  When the learner asks for an explanation that needs a drawing
  Then the reply includes the text and a whiteboard artifact

Scenario: an earlier session can be reopened  [CH-04]
  Given the learner has an existing session
  When they open that session again
  Then its turns are still there

Scenario: switching sessions ends the one they left  [CH-05]
  Given the learner is in a session
  When they switch to another session
  Then the session they left has ended

Scenario: the reply appears while it is still being produced  [CH-03]
  Given the learner has sent a message
  When the agent is still producing the reply
  Then the learner can see the part of the reply already produced

Scenario: a session can be named  [CH-06]
  Given the learner has a session with a first message
  When they name it "Fractions"
  Then the session list and the top bar show "Fractions"

Scenario: an unnamed session shows its first message  [CH-06]
  Given the learner has a session they never named
  When the session list loads
  Then it is labelled with the first message

Scenario: a blank name removes the name  [CH-07]
  Given a session named "Fractions"
  When the learner saves a blank name
  Then the session is labelled with its first message again

Scenario: a long name is refused  [CH-07]
  Given the learner types a name of 81 characters
  When they save it
  Then the name is not stored and the learner is told the limit

Scenario: naming leaves the session as it was  [CH-08]
  Given an ended session
  When the learner names it
  Then it is still ended and has the same turns

Scenario: a reply is drawn with structure  [CH-09]
  Given the agent replies with a heading, numbered steps, a ==key term==, and a Python code block
  When the reply is shown
  Then the learner sees a heading, a numbered list, the key term in the accent, and the code with syntax colors

Scenario: a reply with maths and a table  [CH-09]
  Given the agent replies with $x^2$ and a two-column table
  When the reply is shown
  Then the maths is typeset and the table wraps on a phone instead of scrolling sideways

Scenario: raw HTML stays text  [CH-10]
  Given the reply contains <img src=x onerror=alert(1)>
  When the reply is shown
  Then no image is drawn and the learner sees the text as written

Scenario: deleting a session removes it  [CH-11, CH-12]
  Given the learner has a session with turns and a quiz
  When they delete it from the session list and confirm
  Then it is gone from the list
  And reopening it finds no turns and no quiz

Scenario: the confirmation can be cancelled  [CH-11]
  Given the learner chose to delete a session
  When they cancel the confirmation
  Then the session is still there with the same turns

Scenario: deleting keeps the profile  [CH-12]
  Given a signed-in session whose pass stored a fact
  When the learner deletes that session
  Then the fact is still in the profile

Scenario: deleting the open session opens a new one  [CH-13]
  Given the learner is in a session
  When they delete it
  Then the session has ended and the pass has run
  And a new empty session is open

Scenario: deleting stops a reply in progress  [CH-14]
  Given the agent is still producing a reply
  When the learner deletes the session
  Then the reply stops and the session is gone
  And no turn is saved for it later

Scenario: another learner's session cannot be deleted  [CH-15]
  Given a session that belongs to another learner
  When a delete is requested for it
  Then it is refused and the session is unchanged

Scenario: an anonymous session can be deleted  [CH-15]
  Given an anonymous session
  When the learner deletes it
  Then it is gone and no profile pass runs

Scenario: a failed pass does not block the delete  [CH-16]
  Given a signed-in session whose profile pass fails
  When the learner deletes it
  Then the session is deleted
  And the learner is told its facts were not saved

Scenario: opening a deleted session  [CH-17]
  Given a session deleted in another tab
  When the learner opens it from a stale list
  Then they are told it no longer exists
  And a new empty session opens
