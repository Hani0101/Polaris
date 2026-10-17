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
WB-17  The agent can describe a drawing as a structure (a flow, a sequence, a cycle, a tree, a comparison, or labeled parts). The backend places it, with each label inside its box and each arrow attached to the boxes it joins.

The drawing schema is the Pydantic models in `api/polaris/whiteboard.py`. `check_drawing` in that module checks drawing data before it is drawn. Each step's `reply_part` is `[[step:<step id>]]`. The agent writes that same marker in the reply. While the reply is streaming, the step appears once that marker has arrived, and any step still hidden appears when the reply finishes. Opening a stored whiteboard shows every step. Pointing at a part is metadata on the turn. It does not change the drawing format. The turn names those parts with the same text form as the whiteboard description.

A mark is its own element, kind `mark`, with `mark` of circle, arrow, or note, and it targets one learner element. The agent adds marks as a new step and does not change the learner's elements or comments. A whiteboard that contains a mark is version 3, or version 4 when that drawing already has a description. `check_drawing` still accepts versions 2, 3, and 4. A version 2 drawing with no marks stays version 2.

A version 4 whiteboard includes a `description`, and so do versions 5, 6, and 7. Version 2 and version 3 drawings with no description still open. The text a screen reader reads is that stored description plus a sentence built in code from the learner's shapes and comments. `readable_description` in `api/polaris/whiteboard.py` builds it. An older drawing with no description uses a summary of the drawing, so the board is never unnamed. Marking does not invent a description.

A simpler version is a new whiteboard with a description. Its optional `simplifies` field is the id of the earlier whiteboard, or the field is absent. The format version is not increased. The earlier whiteboard is not changed or deleted. The new drawing is refused unless it has fewer elements than the earlier one, and at least one. Elements include marks. Comments do not count. The learner asks with the Simpler action, which sends the turn. That turn attaches `describe_whiteboard` of the earlier whiteboard and does not send an image.

WB-18  The learner can create a new whiteboard from the Whiteboard tab, as many as they like. Each is an empty board stored as an artifact of the session (WB-04).
WB-19  A whiteboard the learner creates or opens is pinned above the conversation, with the composer below it. One board is pinned at a time. While a board is pinned, every turn is about it. The learner can expand it, draw and comment on it as usual (WB-02), collapse it, and close it. Closing it unpins it, and later turns are no longer about it.
WB-20  The agent can add its own parts to the pinned board, as a new step, next to what the learner drew. It never changes or deletes the learner's parts or comments. The learner can tell the agent's parts from their own, as with marks (WB-09).
WB-21  A save of the learner's drawing never removes a part the agent added, including one added after the learner's browser last loaded the board.

WB-07, WB-14, and WB-15 are kept for later rules: replay step by step, the learner finishing a drawing, and undo history.

A drawing that contains a math or code element is version 5 and includes a description, under the same rules as version 4. `check_drawing` still accepts versions 2, 3, 4, and 5. A version 5 drawing with no math or code is allowed when the description is valid. Marks and a simpler redraw keep working on version 5. Version 2, 3, and 4 drawings with no math or code still open.

A drawing that contains a graph is version 6 and includes a description, under the same rules as version 4 and 5. `check_drawing` still accepts versions 2, 3, 4, 5, and 6. A version 6 drawing with no graph is allowed when the description is valid. A graph on an older version is refused. The backend stores each series' plotted points. The browser draws those points and does not evaluate the expression. Marks, math, code, and a simpler redraw keep working on version 6.

A new drawing from the agent is version 7 and includes a description ([decision 0006](../decisions/0006-one-drawing-format-version.md)). Every element kind is allowed on version 7 and is checked on its own terms. A new kind or field joins version 7 without a new version. `check_drawing` still accepts versions 2 to 6 under the rules above. Marks on a version 7 drawing keep it version 7.

On version 7, a rectangle or ellipse may have a `label`, drawn inside it and centered. An arrow may have a `label`, and `start_element_id` and `end_element_id` that attach its ends to another element that is not an arrow, line, or mark. An attached arrow still stores `start` and `end`, at the edges of the parts it joins. The browser keeps an attached end on its part. An arrow may also have a `bend`: how far its middle curves away from a straight line, positive to the right of its direction. Labels, attachments, and bends on an older version are refused.

### The whiteboard tools

The agent has four whiteboard tools; the fourth, `extend_whiteboard`, is described under "The agent draws on the pinned board". `draw_whiteboard` draws a new whiteboard. `mark_whiteboard` adds marks to a stored whiteboard (WB-09); it takes the whiteboard id, a new step id, its `reply_part`, and the marks, and Polaris sets each mark's kind and author. `simplify_whiteboard` draws a simpler redraw (WB-11) and needs `simplifies`. Each schema types its fields, but list fields still accept JSON text and little is required, so a drawing with mistakes reaches `check_drawing` and its fix limit. The four tools share one fix count per turn.

### The pinned whiteboard

A new whiteboard is version 7 with no parts and the description "Blank whiteboard". It has one empty step, `learner`, so the learner's parts have a step to join. `readable_description` rebuilds the text a screen reader reads from the learner's shapes and comments as they draw (WB-10). Creating a board pins it. Opening a board from the Whiteboard tab or from an artifact card in the chat pins it in place of the one pinned before. Closing the pinned board leaves the other boards as artifacts.

A board the learner creates belongs to no turn. It is marked as learner-made, so a turn that fails or is stopped does not delete it, and no turn claims it. The Whiteboard tab lists every board in the session, newest first, and marks the pinned one.

While a board is pinned, the turn sends `pinned_whiteboard_id` and attaches the full text description of that board, and the picture of the learner's drawing under the rules in "A picture of the learner's drawing". The browser sends a picture only of the pinned board. Pointing at a part (WB-08) narrows the turn to that part. With no board pinned, those two attachments are not sent, and the prompt follows "Whiteboards in the prompt".

The pinned board is about a third of the screen height on a phone, with controls to expand it to the full screen and to collapse it back (WB-16). A new board the agent draws as its own artifact does not replace the pinned board. It appears as an artifact card in the chat.

### The agent draws on the pinned board

The fourth whiteboard tool, `extend_whiteboard`, takes the whiteboard id, a new step id, its `reply_part`, and the agent's parts (`elements`, or a `layout` as in "Placed layouts"), and Polaris sets each part's author. The step appears as its `reply_part` arrives (WB-06). The parts are placed in free space next to the learner's drawing and are checked like any new drawing: `check_drawing` and `layout_problems` apply to the agent's parts, and the learner's parts are never at fault. The tool shares the one fix count per turn with the other whiteboard tools. This adds a field to version 7 and does not add a version ([decision 0006](../decisions/0006-one-drawing-format-version.md)).

`apply_extension` in `api/polaris/extend.py` does this in order. It checks the agent's parts as a drawing of their own, in the usual drawing area, so the learner's parts cannot fail the check. An arrow may attach only to the agent's new parts, so a learner who later erases a part never breaks the board. At most 24 parts go in one step. It then moves the parts as one group to the right of everything already on the board, tops aligned, with a gap of 80, unless they already sit clear of it. The step is stored with `extension: true`, the new version 7 field. A step with that field holds only the agent's own parts, never a mark, and is refused on an older version. A board older than version 7 cannot be added to; the agent draws a new whiteboard instead.

The browser draws the parts of an added step in the tutor's pen, dashed, whatever stroke they were stored with. The learner's pens are always solid, and marks stay red, so the learner can tell the agent's parts from their own and from a mark.

If the turn fails or is stopped, only the added step is taken back. Learner saves made during the turn stay.

A learner save replaces only the learner's parts and comments. The backend keeps every agent part already stored, so a stale save loses nothing. The browser shows a new agent step on the pinned board as it arrives.

A copy may leave out stored steps, agent parts, and agent comments; the stored ones are kept. A copy may not add a step, reorder steps, change a step's reply text or its `extension` field, change an agent part, or put a learner part in an added step. Each step is stored as its agent parts in their stored order, then the copy's learner parts. The save and the agent's step are written one at a time, so neither overwrites the other.

### Layout checks

After a new drawing passes `check_drawing`, `layout_problems` in `api/polaris/layout_check.py` checks where the agent's parts sit. It finds shapes that overlap, text or a label that does not fit its box, parts outside the drawing area from (0, 0) to (1000, 1400), arrow ends that are not attached and touch no part, and more than 24 agent parts. A box that contains another part is not an overlap, except two texts. Learner elements are never at fault. Text size is an estimate from tldraw's font sizes. The browser is not asked.

Marks are checked by `mark_problems` before they are stored: a circle must overlap its target, an arrow mark's end must reach its target, a note must not cover the learner's drawing or another note, and a note's text must fit.

The agent gets layout problems back like a format error and they count toward the same fix limit. When a refusal would leave no fix, a drawing whose only problems are layout problems is stored and shown, and the agent is told what is still wrong.

The drawing evals in `api/evals/drawing_eval.py` use the same checks as a score. `score` reads the whiteboards stored in a data directory. `run` sends the cases in `api/evals/drawing_prompts.json` to the teaching agent through the Claude login and scores what it draws. Both fail when the share of clean drawings is below `--min-clean`.

### Placed layouts

Instead of coordinates, the agent may send `layout` with a new drawing (WB-17). `expand_layout` in `api/polaris/auto_layout.py` places it into ordinary version 7 elements before `check_drawing` runs, so WB-05 still holds and the stored positions are the ones the browser draws. Steps, marks, pointing, and a simpler redraw work on a placed drawing like on any other.

- flow: nodes and links, placed in layers from the first nodes down or to the right.
- sequence and cycle: nodes in order. The backend links them.
- tree: nodes with a parent each, except the root.
- comparison: 2 or 3 columns, each with a title and items, rows lined up.
- parts: a whole and the labeled parts around it, each linked to the whole.

A flow link that skips layers keeps a box-wide gap in each layer it passes, so its arrow runs between boxes. A flow link that goes back to an earlier layer gets a bend, so it curves beside the boxes between its ends.

A node, link, or column may name a step. Without one it is in the first step. An arrow appears with the later of the two parts it joins. Elements the agent lists in a step are kept beside the placed ones. A layout that cannot be placed, or that would not fit the drawing area, is refused with what to change.

### Following the steps

While a reply reveals steps (WB-06), the whole board is fitted when it stays at 75% zoom or more. When it would be smaller, the camera moves to each new step instead, so its text stays readable on a phone (WB-16). A redraw with no new step does not move the camera. The move takes 300ms and does not animate under reduced motion. Opening a stored whiteboard fits it whole.

### The learner draws first

When sketching first would help, the agent asks the learner to draw how they think something works before it explains, and says exactly what to draw. It may draw a board with only a short prompt for the learner to draw on. It then reads the sketch (WB-03) and gives feedback with marks (WB-09).

### A picture of the learner's drawing

When the learner draws on a whiteboard, the browser exports the board as a PNG after each saved change. The next message sends that picture with the turn, and the composer shows that it will. The learner can remove it. A Simpler request does not send it. The backend accepts a PNG of a whiteboard in the same session, at most 2 MB and 2000 pixels on each side. The picture goes to the agent with the turn text as one message, and it is not stored. Later turns see the text description only.

The turn keeps the full text description of the pictured board, so marks still name element ids (WB-09). Hand-drawn sketches are easy to misread, so the agent says what it thinks the learner drew and checks with them before relying on it.

### Whiteboards in the prompt

The prompt for a turn gives the full text description of the latest whiteboard, the whiteboard the learner pointed at, and the pictured whiteboard. Every other whiteboard in the session gets one line: its description or a summary, how many parts, how many are the learner's, and how many comments. A simpler redraw still attaches the full description of the original.

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

Scenario: the agent describes a structure and the backend places it  [WB-17]
  Given the agent explains a process with boxes and arrows
  When it sends the process as a flow layout
  Then the whiteboard shows each label inside its box
  And each arrow stays attached to the boxes it joins
  And no two boxes overlap

Scenario: a crowded drawing is sent back  [WB-05, WB-16]
  Given the agent drew two shapes that overlap
  When fixes remain this turn
  Then the drawing is not shown
  And the agent is told which parts overlap

Scenario: the camera follows a step on a phone  [WB-06, WB-16]
  Given a reply draws a whiteboard too big to read whole on a phone
  When the next step appears
  Then the view moves to that step
  And its text is shown at a readable size

Scenario: a misplaced mark is sent back  [WB-09]
  Given the agent marks the learner's drawing
  When a note covers what the learner drew and fixes remain
  Then the marks are not stored
  And the agent is told which note to move

Scenario: the agent sees the learner's sketch  [WB-03, WB-09]
  Given the learner drew on a whiteboard
  When they send their next message
  Then the agent receives a picture of that whiteboard with its text description
  And the reply says what the agent thinks the learner drew

Scenario: the whiteboard works on a phone  [WB-16]
  Given the learner opens a whiteboard on a phone screen
  When they zoom and move around the drawing
  Then the whole drawing can be reached
  And they do not lose their place

Scenario: the learner creates several boards  [WB-18]
  Given a session
  When the learner presses New whiteboard twice in the Whiteboard tab
  Then the session has two empty whiteboards
  And each can be opened again from the session

Scenario: a created board is pinned above the chat  [WB-19, WB-16]
  Given the learner created a whiteboard
  When they look at the chat
  Then the board is above the conversation and the composer is below it
  And they can expand it, draw on it, and collapse it

Scenario: a message is about the pinned board  [WB-19, WB-03]
  Given a whiteboard is pinned and the learner drew on it
  When they send a message
  Then the agent receives the description of that board and a picture of the learner's drawing

Scenario: a closed board is not attached  [WB-19]
  Given the learner closed the pinned board
  When they send a message
  Then the turn has no picture and no pinned-board description

Scenario: the agent draws next to the learner's work  [WB-20, WB-06]
  Given a pinned board with the learner's drawing
  When the agent explains with its own parts
  Then the parts appear next to the learner's drawing as the text reaches them
  And the learner's parts and comments are unchanged
  And the agent's parts look different from the learner's

Scenario: a stale save keeps the agent's parts  [WB-21]
  Given the agent added a step after the learner's browser loaded the board
  When the learner's browser saves its older copy
  Then the agent's step is still on the board

## Open questions

- Text size in the layout checks is an estimate. A label in a font wider than the estimate could still spill in the browser.
- A bent arrow's stored `start` and `end` sit on the straight line between its parts, not where the curve meets their edges.

- The math check uses pylatexenc, not KaTeX's parser. A string KaTeX rejects might still pass, or the reverse.
- A graph expression may use arithmetic (`+`, `-`, `*`, `/`, `//`, `%`, `**`) plus the named functions. One non-finite sample refuses the whole graph. An axis label may be empty. Plotted values are finite numbers and are not clamped to the coordinate range. The axis ranges are.
