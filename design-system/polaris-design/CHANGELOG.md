# Changelog: polaris-design

Newest first. Deciding a value for the first time is not a change and is not logged. Changing a value that was already confirmed is.

| Date | What changed | Old value | New value | Why |
|---|---|---|---|---|
| 2026-10-19 | Color rule in 2.3, layout rule in 6.5, Side panel rules: Settings becomes a menu of dialogs | A full Settings page with a Back button and one column of sections | The footer Settings button opens a Dropdown menu upward; Appearance and Profile each open a Modal with only a Close button; a confirm can open over it | The learner wants to change settings without leaving the conversation (ST-01) |
| 2026-10-18 | Color rules in 2.3, layout rule in 6.5, Side panel rules, Checkbox and radio rules: the learner chooses the appearance mode on a Settings page | The mode followed the operating system only; no Settings page | System, Light, or Dark chosen on a Settings page opened from a footer button in the left panel; a named radio group; a new whiteboard follows the mode, an existing one does not | Light mode is wanted (ST-02, WB-22, decision 0010) |
| 2026-10-17 | Color rule in 2.3: the look of parts the agent adds to the learner's pinned board | none | Pen box 1, dashed, whatever stroke was sent | The learner must tell the agent's added parts from their own (WB-20) |
| 2026-10-17 | Quiz question card, Answer option, Result feedback (section 7): when a quiz answer is checked, and where its feedback sits | "Check answer" button at the end, a separate feedback box under the options, "See results" on the last question | A pick checks at once, feedback text inside the options, quiz results appear under the last question | Quiz feedback is immediate (decision 0009) |
| 2026-10-17 | Expanded quiz page layout (section 6): `layout.maxWidth.chat` also used for the quiz column; quiz removed from the 12-column grid and `layout.maxWidth.content` uses | 8 of 12 columns, left-aligned, title full width | One 720px column, centered, title and card inside it | The quiz page felt empty with the column pushed to the left |
| 2026-10-17 | Added `color.code.keyword`, `.string`, `.number`, `.function`, `.comment` (section 2) | none | #7a3e9d / #c9a2ef, #3d6b1f / #a8d48a, #1f5f8b / #8cc4ec, #9a3b5b / #f2a3c0, `color.text.muted` | Syntax colors for code blocks in tutor replies |
| 2026-10-17 | Chat message rules: key term, callout, quote, table, and struck-through looks in tutor replies | none | See Chat message rules | Tutor replies support more Markdown |
| 2026-10-16 | Icon button rule: where primary is used | Only Send | Send, and Stop in its place while the tutor replies | Chat input: Send becomes Stop during a reply |
| 2026-10-16 | Added `radius.xs` (section 5) and checkboxes to the corner rule | none | 4px, checkbox corners only | 8px on a 24px box looks almost round, like a radio button |
| 2026-10-16 | Accent rule in 2.3: allowed uses | ...key-term highlights, and badges or dots | ...key-term highlights, and badges | No dots: the user says they look like AI design |
| 2026-10-16 | Added `typography.buttonSmall` (section 3) | none | body font, 14px, bold, 1.2 line height | Needed by the small button size |
| 2026-10-16 | Added `color.action.destructive.default`, `.hover`, `.active` (section 2) | none | #fbe9e7 / #2a1512, #f7dad6 / #3a1c17, #f5d4cf / #4a231d | Needed by the destructive button variant |
| 2026-10-15 | Created design system | none | none | Started interview |
