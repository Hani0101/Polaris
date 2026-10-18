# Flashcards

A deck of flashcards helps the learner revise what a session covered or what a resource says. It is an artifact of the session. A deck is for review and does not replace the explanation: first exposure stays in the chat. Every card is tied to a source (FC-04, FC-05), so a deck is never written from the model's memory alone. See [A deck's sources are checked by code](../decisions/0012-deck-sources-checked-by-code.md).

## Rules

FC-01  A deck starts in the chat turn that created it. The learner can ask for one in the chat, or choose Create flashcards in the right panel. Choosing it opens a dialog (FC-03), and submitting the dialog sends a visible learner turn that asks for the deck. The agent builds the deck in that turn.
FC-02  The learner can expand that same deck onto its own page.
FC-03  The dialog asks what the flashcards should be about. The learner can type what they want, attach files, and pick resources already in the session, in any mix, but must give at least one of them. An attached file goes through the same add path as the Resources tab, with the same types, limits, and refusals (RS-03 to RS-06, RS-19), and becomes a resource of the session that counts toward its limit of 10 (RS-04).
FC-04  A deck can be built only from the turns of its session and from its resources. Nothing else is a source in v1.
FC-05  A flashcard has a front, a back, and a source. The front is a question or a term for one concept. The back is a summary of at most about three sentences. The source is shown on the back: a PDF as the resource and page, for example "Notes.pdf, p. 4", another resource as its name and the quoted phrase (RS-09), and a turn as its number, for example "Turn 3".
FC-06  Before a deck is stored, code checks the source of every card. A cited PDF page must exist, a quoted phrase must appear in that resource's extracted text, and a cited turn must exist in the session. A card that fails is a refusal of the whole deck. The agent is told which card to fix and may send the deck once more in the same reply. No second model is used.
FC-07  When no turn or resource covers what the learner asked for, no deck is stored. The agent says so, offers what works now, which is teaching the topic in the chat first or adding a resource to the session, and says that fetching from the internet is not available yet. It never writes cards from its own memory.
FC-08  A deck is never padded. When the sources support fewer cards than asked for, the deck has fewer, and the agent says how many the sources supported.
FC-09  A deck has 5 to 15 cards unless the learner asks for more. A request for more is honored up to 30 cards. Past 30 the agent says so and offers a second deck.
FC-10  Card text is plain text. A card has no image and no whiteboard. Raw HTML in a card is shown as text and never rendered.
FC-11  A card cannot be edited. To change a deck the learner asks for a new one.
FC-12  Creating a deck stores it as an artifact of that session. A deck that is refused, or fails twice, stores nothing, not even part of it. The agent tells the learner which cards failed and why, and the learner can ask again.
FC-13  The study view shows one card at a time. The learner flips the card to see the back, then rates it "got it" or "again". A card rated "again" comes back later in the same sitting. A sitting ends when no card is rated "again".
FC-14  Each card keeps its latest rating: got it, again, or unrated. A deck that is opened again shows the ratings and how many cards are still to review, and a card can be rated again. The learner can reset every rating of the deck.
FC-15  Every later reply in the session reads the state of each deck: the front of each card rated "again" and the number of cards unrated.
FC-16  A rating never reaches the profile. A deck works the same in an anonymous session and a signed-in one (PR-09, PR-10).
FC-17  Deleting a session deletes its decks and their ratings (CH-12).
FC-18  Removing a resource that a card cites leaves the card as it was. The source line of that card shows "resource removed" (RS-15).
FC-19  The study view fits a phone from 320px wide with no horizontal scroll. Every control is reachable by keyboard, is at least 44px, and meets WCAG AA.

## Scenarios

Scenario: the dialog creates a visible turn  [FC-01]
  Given the right panel is open
  When the learner chooses Create flashcards, types a topic, and submits
  Then a learner turn asking for the deck is added to the chat
  And the deck appears in that turn's reply

Scenario: a deck is asked for in the chat  [FC-01]
  Given a session that explained photosynthesis
  When the learner types "make flashcards for what we covered"
  Then the reply has a deck

Scenario: the learner expands the deck  [FC-01, FC-02]
  Given a deck shown in the chat
  When the learner expands it
  Then the same deck is on its own page

Scenario: the dialog needs something to go on  [FC-03]
  Given the Create flashcards dialog
  When the learner submits it with no text, no file, and no resource picked
  Then it is not submitted and the learner is told why

Scenario: a mix of inputs is allowed  [FC-03]
  Given a session with a note called "Week 2"
  When the learner types a topic, attaches a PDF, and picks "Week 2"
  Then the turn asks for a deck from all three

Scenario: an attached file becomes a resource  [FC-03]
  Given a session with no resources
  When the learner attaches a PDF in the dialog and submits
  Then the PDF is listed in the Resources tab

Scenario: the dialog refuses what the Resources tab refuses  [FC-03]
  Given the Create flashcards dialog
  When the learner attaches a spreadsheet, or an 11 MB PDF
  Then it is refused with the same reason the Resources tab gives

Scenario: a deck uses only the session's sources  [FC-04]
  Given a resource in another session that covers mitosis
  When the learner asks this session for mitosis flashcards
  Then no card cites that resource

Scenario: each card shows its source  [FC-05]
  Given a deck built from page 4 of "Notes.pdf", a note called "Week 2", and turn 3
  When the learner flips a card from each
  Then the backs show "Notes.pdf, p. 4", "Week 2" with a quoted phrase, and "Turn 3"

Scenario: a page that does not exist is refused  [FC-06]
  Given the agent creates a deck whose card cites page 40 of a 12-page PDF
  When the deck is stored
  Then the deck is not stored
  And the agent is told which card to fix

Scenario: a phrase that is not in the resource is refused  [FC-06]
  Given the agent creates a deck whose card quotes a phrase the resource does not contain
  When the deck is stored
  Then the deck is not stored

Scenario: a turn that does not exist is refused  [FC-06]
  Given a session of 4 turns
  When the agent creates a deck whose card cites turn 9
  Then the deck is not stored

Scenario: a refused deck may be sent once more  [FC-06]
  Given the agent's first deck was refused
  When the agent sends a corrected deck in the same reply
  Then the corrected deck is stored

Scenario: no source means no deck  [FC-07]
  Given a session with no turns on and no resource about volcanoes
  When the learner asks for volcano flashcards
  Then no deck is stored
  And the agent offers to teach the topic or take a resource
  And it says fetching from the internet is not available yet

Scenario: a deck is not padded  [FC-08]
  Given a note that supports only 8 cards
  When the learner asks for 15 flashcards from it
  Then the deck has 8 cards
  And the agent says the note supported 8

Scenario: the default size  [FC-09]
  Given a long resource
  When the learner asks for flashcards without a number
  Then the deck has between 5 and 15 cards

Scenario: more cards on request, up to 30  [FC-09]
  Given a long resource
  When the learner asks for 25 flashcards
  Then the deck has 25 cards

Scenario: past 30 is a second deck  [FC-09]
  Given a long resource
  When the learner asks for 50 flashcards
  Then the deck has at most 30 cards
  And the agent offers a second deck

Scenario: card text is not rendered as markup  [FC-10]
  Given a card whose back contains <img src=x onerror=alert(1)>
  When the learner flips it
  Then no image is drawn and the learner sees the text as written

Scenario: a card has no edit control  [FC-11]
  Given a deck
  When the learner looks for a way to edit a card
  Then there is none

Scenario: a created deck is stored  [FC-12]
  Given the agent created a deck
  When the learner reopens the session
  Then the deck is in the tools panel

Scenario: a failed deck stores nothing  [FC-12]
  Given the agent's deck failed the source check twice
  When the reply ends
  Then no deck is stored, not even part of one
  And the reply says which cards failed and why

Scenario: flip then rate  [FC-13]
  Given a deck open in the study view
  When the learner flips a card and rates it "again"
  Then the card comes back later in the same sitting

Scenario: the sitting ends  [FC-13]
  Given a deck whose last "again" card the learner has rated "got it"
  When they rate it
  Then the sitting ends and the learner sees how many cards were rated each way

Scenario: ratings are kept  [FC-14]
  Given a deck with two cards rated and one unrated
  When the learner opens the deck again
  Then the ratings show and one card is still to review

Scenario: ratings can be reset  [FC-14]
  Given a deck with rated cards
  When the learner resets the ratings
  Then every card is unrated

Scenario: the next reply sees the deck  [FC-15]
  Given a deck with one card rated "again" and two unrated
  When the learner sends the next message
  Then the reply reads the front of the "again" card and that two are unrated

Scenario: ratings stay out of the profile  [FC-16]
  Given a signed-in session with a deck whose cards were rated
  When the learner leaves the session
  Then no fact stored in the profile came from a rating

Scenario: an anonymous session has decks  [FC-16]
  Given an anonymous session
  When the learner asks for flashcards
  Then the deck is made and nothing reaches the profile

Scenario: deleting a session deletes its decks  [FC-17, CH-12]
  Given a session with a deck
  When the learner deletes the session and confirms
  Then the deck and its ratings are gone

Scenario: a removed resource leaves the card  [FC-18]
  Given a card that cites "Notes.pdf, p. 4"
  When the learner removes "Notes.pdf" and confirms
  Then the card is still in the deck
  And its source line shows "resource removed"

Scenario: the study view fits a phone  [FC-19]
  Given a phone screen 320px wide
  When the learner opens a deck
  Then it fits without horizontal scroll
  And flip and both rating controls work from the keyboard and are at least 44px
