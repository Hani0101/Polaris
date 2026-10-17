# Changelog: polaris-design

Newest first. Deciding a value for the first time is not a change and is not logged. Changing a value that was already confirmed is.

| Date | What changed | Old value | New value | Why |
|---|---|---|---|---|
| 2026-10-17 | Expanded quiz page layout (section 6): `layout.maxWidth.chat` also used for the quiz column; quiz removed from the 12-column grid and `layout.maxWidth.content` uses | 8 of 12 columns, left-aligned, title full width | One 720px column, centered, title and card inside it | The quiz page felt empty with the column pushed to the left |
| 2026-10-17 | Added `color.code.keyword`, `.string`, `.number`, `.function`, `.comment` (section 2) | none | #7a3e9d / #c9a2ef, #3d6b1f / #a8d48a, #1f5f8b / #8cc4ec, #9a3b5b / #f2a3c0, `color.text.muted` | Syntax colors for code blocks in tutor replies |
| 2026-10-17 | Chat message rules: key term, callout, quote, table, and struck-through looks in tutor replies | none | See Chat message rules | Tutor replies support more Markdown |
| 2026-10-16 | Icon button rule: where primary is used | Only Send | Send, and Stop in its place while the tutor replies | Chat input: Send becomes Stop during a reply |
| 2026-10-16 | Added `radius.xs` (section 5) and checkboxes to the corner rule | none | 4px, checkbox corners only | 8px on a 24px box looks almost round, like a radio button |
| 2026-10-16 | Accent rule in 2.3: allowed uses | ...key-term highlights, and badges or dots | ...key-term highlights, and badges | No dots: the user says they look like AI design |
| 2026-10-16 | Added `typography.buttonSmall` (section 3) | none | body font, 14px, bold, 1.2 line height | Needed by the small button size |
| 2026-10-16 | Added `color.action.destructive.default`, `.hover`, `.active` (section 2) | none | #fbe9e7 / #2a1512, #f7dad6 / #3a1c17, #f5d4cf / #4a231d | Needed by the destructive button variant |
| 2026-10-15 | Created design system | none | none | Started interview |
