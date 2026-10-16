# Whiteboard

A whiteboard is a drawing the agent and the learner work on together. It is an artifact of the session.

## Rules

WB-01  The agent can draw on the whiteboard.
WB-02  The learner can draw on the whiteboard and leave a comment.
WB-03  A later turn in the session can see the learner's drawing and comment.
WB-04  Creating a whiteboard stores it as an artifact of that session. The learner can open it again from the session.
WB-05  The backend checks the drawing data before the browser draws it.
WB-06  The agent draws in steps. Each step is tied to one part of the reply text, and the step appears when that part of the text appears.
WB-08  The learner can point at any part of the drawing and ask about it. The next turn knows which part was pointed at.
WB-09  The agent can mark up the learner's drawing (circle, arrow, note) without changing what the learner drew. The learner can tell the agent's marks from their own.
WB-10  Every drawing has a text description that a screen reader can read (WCAG AA).
WB-11  The learner can ask for a simpler version. The agent redraws the same idea with fewer parts, and the earlier drawing stays in the session.
WB-12  The agent can draw math and code as real text (formulas, code blocks), not as hand-drawn shapes.
WB-13  The agent can draw a graph of a function or data from numbers it provides, so the graph is exact.
WB-16  The whiteboard fits a phone screen. The learner can zoom and move around without losing their place.

The drawing schema is the Pydantic models in `api/polaris/whiteboard.py`. `check_drawing` in that module checks drawing data before it is drawn. Each step's `reply_part` is `[[step:<step id>]]`. The agent writes that same marker in the reply. While the reply is streaming, the step appears once that marker has arrived, and any step still hidden appears when the reply finishes. Opening a stored whiteboard shows every step. Pointing at a part is metadata on the turn. It does not change the drawing format. The turn names those parts with the same text form as the whiteboard description.

A mark is its own element, kind `mark`, with `mark` of circle, arrow, or note, and it targets one learner element. The agent adds marks as a new step and does not change the learner's elements or comments. A whiteboard that contains a mark is version 3, or version 4 when that drawing already has a description. `check_drawing` still accepts versions 2, 3, and 4. A version 2 drawing with no marks stays version 2.

A new whiteboard from the agent is version 4 and includes a `description`. Version 2 and version 3 drawings with no description still open. The text a screen reader reads is that stored description plus a sentence built in code from the learner's shapes and comments. `readable_description` in `api/polaris/whiteboard.py` builds it. An older drawing with no description uses a summary of the drawing, so the board is never unnamed. Marking does not invent a description.

A simpler version is a new version 4 whiteboard. Its optional `simplifies` field is the id of the earlier whiteboard, or the field is absent. The format version is not increased. The earlier whiteboard is not changed or deleted. The new drawing is refused unless it has fewer elements than the earlier one, and at least one. Elements include marks. Comments do not count. The learner asks with the Simpler action, which sends the turn. That turn attaches `describe_whiteboard` of the earlier whiteboard and does not send an image.

WB-07, WB-14, WB-15, and WB-17 are kept for later rules: replay step by step, the learner finishing a drawing, undo history, and a small set of shapes and layouts.

A drawing that contains a math or code element is version 5 and includes a description, under the same rules as version 4. `check_drawing` still accepts versions 2, 3, 4, and 5. A version 5 drawing with no math or code is allowed when the description is valid. Marks and a simpler redraw keep working on version 5. Version 2, 3, and 4 drawings with no math or code still open.

A drawing that contains a graph is version 6 and includes a description, under the same rules as version 4 and 5. `check_drawing` still accepts versions 2, 3, 4, 5, and 6. A version 6 drawing with no graph is allowed when the description is valid. A graph on an older version is refused. The backend stores each series' plotted points. The browser draws those points and does not evaluate the expression. Marks, math, code, and a simpler redraw keep working on version 6.

## Scenarios

Scenario: the agent draws  [WB-01]
  Given a session
  When the agent decides a drawing will help
  Then the whiteboard shows the agent's drawing

Scenario: a learner comment survives  [WB-02, WB-03]
  Given a whiteboard in the session
  When the learner draws on it and leaves a comment
  Then a later turn in that session still shows that drawing and that comment

Scenario: bad drawing data is refused  [WB-05]
  Given the agent produced drawing data
  When the data fails the check
  Then the browser does not draw it

Scenario: steps follow the text  [WB-06]
  Given the agent explains an idea with a drawing
  When the reply text reaches a new part
  Then the drawing step for that part appears

Scenario: the learner points and asks  [WB-08]
  Given a drawing in the session
  When the learner selects one part and asks about it
  Then the reply is about that part

Scenario: agent marks do not change the learner's drawing  [WB-09]
  Given the learner drew an answer
  When the agent marks a mistake on it
  Then the learner's drawing is unchanged
  And the agent's mark looks different from the learner's lines

Scenario: a screen reader reads the drawing  [WB-10]
  Given a drawing in the session
  When a screen reader reaches it
  Then it reads the drawing's text description

Scenario: a simpler redraw keeps the first one  [WB-11]
  Given a drawing in the session
  When the learner asks for a simpler version
  Then a new drawing with fewer parts appears
  And the first drawing can still be opened

Scenario: math and code are real text  [WB-12]
  Given the agent explains a formula or a piece of code
  When it draws it on the whiteboard
  Then the formula or code is shown as rendered text, not as shapes

Scenario: a graph matches its numbers  [WB-13]
  Given the agent draws a graph from a function or from data
  When the graph appears
  Then every plotted point matches the numbers the agent provided

Scenario: the whiteboard works on a phone  [WB-16]
  Given the learner opens a whiteboard on a phone screen
  When they zoom and move around the drawing
  Then the whole drawing can be reached
  And they do not lose their place

## Open questions

- The math check uses pylatexenc, not KaTeX's parser. A string KaTeX rejects might still pass, or the reverse.
- A graph expression may use arithmetic (`+`, `-`, `*`, `/`, `//`, `%`, `**`) plus the named functions. One non-finite sample refuses the whole graph. An axis label may be empty. Plotted values are finite numbers and are not clamped to the coordinate range. The axis ranges are.
