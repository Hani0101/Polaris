# Design system: polaris-design

Status: In progress
Last updated: 2026-10-16
Tokens file: tokens.json
Banned defaults: banned.md

## 1. Product context

### What it is
Polaris guides a person to learn a new topic, or gives general help with tasks they have. For now it supports whiteboard drawing, showing illustrations and animations, and quizzes.

This design system covers the whole product: sign-in, chat, whiteboard, quiz, animation, and artifacts.

### Who uses it
A student, or anyone who wants to learn or get guidance on a specific topic, using Polaris on their phone or laptop.

### How it should feel
| Word | What it means in practice | Why |
|---|---|---|
| Reassuring | Mistakes are never shown in harsh red alone. A wrong quiz answer uses a soft red together with a helpful line, for example "Not quite, here's why". | Every person can learn the material, however hard they think it is. |
| Guiding | Progress is always visible, for example "Question 2 of 5" or the learner's place in a lesson. Tutor replies are structured: headings, numbered steps, short paragraphs, never walls of text. | The AI is there to guide the learner in the most effective way. |
| Trustworthy | Plain, consistent styling: the same component looks the same everywhere, no flashy gradients or gimmicks. Honest about limits: when the tutor is unsure or something fails, it says so in plain words. Easy to read: high contrast, body text at least 16px. | Learners want an accessible, reliable AI that does not lie to them when it is unsure. |
| Calm | One accent color, everything else neutral. Generous empty space so nothing feels packed (exact steps set in section 4). | Learners are often stressed or tired, and a busy screen makes studying harder. |
| Supportive | Warm, encouraging copy, not childish, no overuse of emoji. Help is always one tap away: a visible way to ask the tutor about anything on screen. Rounded, soft shapes rather than sharp corners (exact radius set in section 5). | Learners want help reaching their goal, whether for school, a job interview, work, or personal interest. |

### Reference products
| Product or site | What exactly to take from it | What not to take from it |
|---|---|---|
| NotebookLM (notebooklm.google.com) | The layout: tools in a panel on the right side, the learner's own materials on the left side. | The home page listing every notebook: messy and too much to look at. |
| TBD | TBD | TBD |

## 2. Colors

### 2.1 Color tokens
Dark mode: yes

| Token | Light | Dark | Used for | Why |
|---|---|---|---|---|
| `color.bg.page` | #faf8f4 | #0c0701 | Main background behind everything | Light: not given. Dark: the night sky, Polaris is the North Star |
| `color.bg.subtle` | #f2eee6 | #130e08 | Slightly tinted areas: chat input bar, sidebar | Not given |
| `color.surface.default` | #ffffff | #19130c | Cards and panels: quiz card, session in the list | Not given |
| `color.surface.raised` | #ffffff | #211910 | Floating things: menus, tooltips | Not given |
| `color.surface.overlay` | #0c070166 | #000000b3 | Dim layer behind a dialog (ink at 40% light, black at 70% dark) | Not given |
| `color.text.primary` | #0c0701 | #faf8f4 | Main reading text, tutor replies | Light: the brand ink, the night sky identity. Dark: same warm white as the board, brightest option |
| `color.text.secondary` | #4a4038 | #c9bfb2 | Timestamps, captions | Stronger option, easier to read |
| `color.text.muted` | #5c5249 | #9a8f82 | Placeholders, hints | Stronger option, still passes 4.5:1 so everyone can read it |
| `color.text.disabled` | #a89f94 | #5e554b | Text on things that cannot be used right now | Faded so it reads as unusable; WCAG sets no minimum for disabled |
| `color.text.inverse` | #faf8f4 | #0c0701 | Text on an opposite-colored fill, like a tooltip | Not given |
| `color.text.onAction` | #faf8f4 | #0c0701 | Text on the primary button | Highest contrast on the primary fill in each mode (18.9:1) |
| `color.text.onAccent` | #faf8f4 | #0c0701 | Text on an accent fill, like a badge | Ink fails on the light accent (3.6:1), warm white passes (5.3:1); in dark, ink on amber passes (8.1:1) |
| `color.text.link` | #0c0701 | #faf8f4 | Links in text, always underlined | Calmest option, keeps a single accent |
| `color.border.subtle` | #e6e0d6 | #2c241a | Faintest lines: dividers between chat messages | Decorative, soft lines keep the screen calm |
| `color.border.default` | #d9d2c6 | #3a3026 | Card and panel edges (decorative) | Decorative, soft lines keep the screen calm |
| `color.border.strong` | #8c8174 | #7a6f62 | Edges you must see: inputs, checkboxes, quiz answer boxes | Must-see edges need 3:1, these pass on every background |
| `color.action.primary.default` | #0c0701 | #faf8f4 | Primary button fill | Light: the brand ink. Dark: warm white mirrors the light button, amber stays a pure highlight |
| `color.action.primary.hover` | #2a2018 | #ede6da | Primary button, mouse over | A step away from the default, text stays above 12:1 |
| `color.action.primary.active` | #3a3026 | #d9d2c6 | Primary button, while pressed | A further step, text stays above 12:1 |
| `color.action.primary.disabled` | #00000000 | #00000000 | Primary button, disabled: no fill, `color.border.subtle` outline, `color.text.disabled` text | Clearly switched off, never looks like an enabled secondary button |
| `color.action.secondary.default` | #ebe5da | #2c241a | Secondary button fill: Skip, Cancel | Not given |
| `color.action.secondary.hover` | #e2dbcd | #3a3026 | Secondary button, mouse over | Not given |
| `color.action.secondary.active` | #d9d2c6 | #463a2e | Secondary button, while pressed | Not given |
| `color.action.secondary.disabled` | #00000000 | #00000000 | Secondary button, disabled: same look as the primary disabled | Clearly switched off, one disabled look for all buttons |
| `color.action.destructive.default` | #fbe9e7 | #2a1512 | Destructive button fill (same as `color.state.errorBg`) | Soft error colors, never a harsh red (section 1) |
| `color.action.destructive.hover` | #f7dad6 | #3a1c17 | Destructive button, mouse over | A step deeper, error text stays above 4.5:1 |
| `color.action.destructive.active` | #f5d4cf | #4a231d | Destructive button, while pressed | A further step, error text stays above 4.5:1 |
| `color.accent` | #a84e18 | #f08a4b | Dawn amber: progress, selected item, key-term highlights, badges | Dark: the star color, why not given. Light: same hue made deeper so it passes on the light page (5.3:1) |
| `color.state.error` | #a63a2b | #f19a8e | Error text and icons, wrong quiz answers | Soft, muted red, never harsh (section 1, Reassuring) |
| `color.state.errorBg` | #fbe9e7 | #2a1512 | Error background | Soft background carries the color, not a loud red |
| `color.state.success` | #2f6b3a | #8fd19e | Success text and icons, right quiz answers | Passes 4.5:1 on its background and the page |
| `color.state.successBg` | #e6f2e6 | #11241a | Success background | Soft background, calm |
| `color.state.warning` | #8a5a00 | #f0c674 | Warning text and icons | Passes 4.5:1 on its background and the page |
| `color.state.warningBg` | #fbf0d9 | #2a1f0a | Warning background | Soft background, calm |
| `color.state.info` | #2b5a8a | #9cc3ff | Info text and icons | Passes 4.5:1 on its background and the page |
| `color.state.infoBg` | #e6eef7 | #0f1c2e | Info background | Soft background, calm |
| `color.focus.ring` | #0c0701 | #f08a4b | Outline showing where the keyboard is | Highest contrast in each mode (18.9:1 light, 7.0:1 dark at worst) |
| `color.whiteboard.board.default` | #faf8f4 | #0c0701 | Board when a whiteboard opens: white in light mode, night in dark mode | Familiar like a real classroom board |
| `color.whiteboard.board.white` | #faf8f4 | #faf8f4 | Board box 1, warm white | Familiar like a real classroom board |
| `color.whiteboard.board.night` | #0c0701 | #0c0701 | Board box 2, night sky | The dark mode board, the Polaris night sky |
| `color.whiteboard.board.yellow` | #fdf3c7 | #fdf3c7 | Board box 3, soft yellow | A few soft tints give variety without clutter, like colored paper in a classroom |
| `color.whiteboard.board.blue` | #e0efff | #e0efff | Board box 4, pale blue | A few soft tints give variety without clutter, like colored paper in a classroom |
| `color.whiteboard.board.green` | #dff3e4 | #dff3e4 | Board box 5, pale green | A few soft tints give variety without clutter, like colored paper in a classroom |
| `color.whiteboard.board.pink` | #fbe4ec | #fbe4ec | Board box 6, pale pink | A few soft tints give variety without clutter, like colored paper in a classroom |
| `color.whiteboard.pen.onLight.tutor` | #000000 | #000000 | Pen box 1 on light boards, the tutor's pen | Familiar like a real classroom board |
| `color.whiteboard.pen.onLight.learner` | #1d4ed8 | #1d4ed8 | Pen box 2 on light boards, the learner's pen | The learner's blue keeps their marks apart from the tutor's |
| `color.whiteboard.pen.onLight.red` | #dc2626 | #dc2626 | Pen box 3 on light boards | Common drawing color, at least 4.0:1 on every light board |
| `color.whiteboard.pen.onLight.green` | #15803d | #15803d | Pen box 4 on light boards | Common drawing color, at least 4.0:1 on every light board |
| `color.whiteboard.pen.onLight.orange` | #c2410c | #c2410c | Pen box 5 on light boards | Common drawing color; not the accent, which is 2.4:1 on the board |
| `color.whiteboard.pen.onLight.purple` | #7e22ce | #7e22ce | Pen box 6 on light boards | Common drawing color, at least 4.0:1 on every light board |
| `color.whiteboard.pen.onDark.tutor` | #faf8f4 | #faf8f4 | Pen box 1 on dark boards, the tutor's pen | Familiar like a real classroom board |
| `color.whiteboard.pen.onDark.learner` | #60a5fa | #60a5fa | Pen box 2 on dark boards, the learner's pen | `#1d4ed8` is only 3.0:1 on the night board, this lighter blue is 7.9:1 |
| `color.whiteboard.pen.onDark.red` | #f87171 | #f87171 | Pen box 3 on dark boards | Lighter version stays visible on the night board |
| `color.whiteboard.pen.onDark.green` | #4ade80 | #4ade80 | Pen box 4 on dark boards | Lighter version stays visible on the night board |
| `color.whiteboard.pen.onDark.orange` | #fb923c | #fb923c | Pen box 5 on dark boards | Lighter version stays visible on the night board |
| `color.whiteboard.pen.onDark.purple` | #c084fc | #c084fc | Pen box 6 on dark boards | Lighter version stays visible on the night board |

Whiteboard tokens have the same value in both columns: they follow the board, not the app mode.

### 2.2 Contrast checks
| Text | Background | Kind | Light ratio | Dark ratio | Result |
|---|---|---|---|---|---|
| `color.text.primary` | `color.bg.page` | text | 18.92:1 | 18.92:1 | Pass |
| `color.text.primary` | `color.bg.subtle` | text | 17.34:1 | 18.10:1 | Pass |
| `color.text.primary` | `color.surface.default` | text | 20.07:1 | 17.37:1 | Pass |
| `color.text.primary` | `color.surface.raised` | text | 20.07:1 | 16.35:1 | Pass |
| `color.text.secondary` | `color.bg.page` | text | 9.51:1 | 11.06:1 | Pass |
| `color.text.secondary` | `color.bg.subtle` | text | 8.72:1 | 10.58:1 | Pass |
| `color.text.secondary` | `color.surface.default` | text | 10.09:1 | 10.16:1 | Pass |
| `color.text.secondary` | `color.surface.raised` | text | 10.09:1 | 9.56:1 | Pass |
| `color.text.muted` | `color.bg.page` | text | 7.18:1 | 6.33:1 | Pass |
| `color.text.muted` | `color.bg.subtle` | text | 6.58:1 | 6.06:1 | Pass |
| `color.text.muted` | `color.surface.default` | text | 7.61:1 | 5.81:1 | Pass |
| `color.text.muted` | `color.surface.raised` | text | 7.61:1 | 5.47:1 | Pass |
| `color.text.link` | `color.bg.page` | text | 18.92:1 | 18.92:1 | Pass |
| `color.text.link` | `color.bg.subtle` | text | 17.34:1 | 18.10:1 | Pass |
| `color.text.link` | `color.surface.default` | text | 20.07:1 | 17.37:1 | Pass |
| `color.text.link` | `color.surface.raised` | text | 20.07:1 | 16.35:1 | Pass |
| `color.text.onAction` | `color.action.primary.default` | text | 18.92:1 | 18.92:1 | Pass |
| `color.text.onAction` | `color.action.primary.hover` | text | 15.02:1 | 16.18:1 | Pass |
| `color.text.onAction` | `color.action.primary.active` | text | 12.14:1 | 13.36:1 | Pass |
| `color.text.primary` | `color.action.secondary.default` | text | 16.01:1 | 14.41:1 | Pass |
| `color.text.primary` | `color.action.secondary.hover` | text | 14.57:1 | 12.14:1 | Pass |
| `color.text.primary` | `color.action.secondary.active` | text | 13.36:1 | 10.39:1 | Pass |
| `color.text.onAccent` | `color.accent` | text | 5.25:1 | 8.07:1 | Pass |
| `color.accent` | `color.bg.page` | text | 5.25:1 | 8.07:1 | Pass |
| `color.accent` | `color.bg.subtle` | text | 4.82:1 | 7.72:1 | Pass |
| `color.accent` | `color.surface.default` | text | 5.57:1 | 7.41:1 | Pass |
| `color.state.error` | `color.state.errorBg` | text | 5.49:1 | 8.03:1 | Pass |
| `color.state.error` | `color.bg.page` | text | 6.07:1 | 9.32:1 | Pass |
| `color.state.success` | `color.state.successBg` | text | 5.54:1 | 9.13:1 | Pass |
| `color.state.success` | `color.bg.page` | text | 6.03:1 | 11.26:1 | Pass |
| `color.state.warning` | `color.state.warningBg` | text | 5.24:1 | 10.04:1 | Pass |
| `color.state.warning` | `color.bg.page` | text | 5.59:1 | 12.46:1 | Pass |
| `color.state.info` | `color.state.infoBg` | text | 6.12:1 | 9.51:1 | Pass |
| `color.state.info` | `color.bg.page` | text | 6.75:1 | 11.15:1 | Pass |
| `color.border.strong` | `color.bg.page` | ui | 3.59:1 | 4.09:1 | Pass |
| `color.border.strong` | `color.bg.subtle` | ui | 3.30:1 | 3.91:1 | Pass |
| `color.border.strong` | `color.surface.default` | ui | 3.81:1 | 3.75:1 | Pass |
| `color.focus.ring` | `color.bg.page` | ui | 18.92:1 | 8.07:1 | Pass |
| `color.focus.ring` | `color.bg.subtle` | ui | 17.34:1 | 7.72:1 | Pass |
| `color.focus.ring` | `color.surface.default` | ui | 20.07:1 | 7.41:1 | Pass |
| `color.whiteboard.pen.onLight.tutor` | `color.whiteboard.board.white` | ui | 19.80:1 | 19.80:1 | Pass |
| `color.whiteboard.pen.onLight.learner` | `color.whiteboard.board.white` | ui | 6.32:1 | 6.32:1 | Pass |
| `color.whiteboard.pen.onLight.red` | `color.whiteboard.board.white` | ui | 4.55:1 | 4.55:1 | Pass |
| `color.whiteboard.pen.onLight.green` | `color.whiteboard.board.white` | ui | 4.73:1 | 4.73:1 | Pass |
| `color.whiteboard.pen.onLight.orange` | `color.whiteboard.board.white` | ui | 4.88:1 | 4.88:1 | Pass |
| `color.whiteboard.pen.onLight.purple` | `color.whiteboard.board.white` | ui | 6.58:1 | 6.58:1 | Pass |
| `color.whiteboard.pen.onLight.red` | `color.whiteboard.board.yellow` | ui | 4.33:1 | 4.33:1 | Pass |
| `color.whiteboard.pen.onLight.red` | `color.whiteboard.board.blue` | ui | 4.13:1 | 4.13:1 | Pass |
| `color.whiteboard.pen.onLight.red` | `color.whiteboard.board.green` | ui | 4.16:1 | 4.16:1 | Pass |
| `color.whiteboard.pen.onLight.red` | `color.whiteboard.board.pink` | ui | 4.00:1 | 4.00:1 | Pass |
| `color.whiteboard.pen.onDark.tutor` | `color.whiteboard.board.night` | ui | 18.92:1 | 18.92:1 | Pass |
| `color.whiteboard.pen.onDark.learner` | `color.whiteboard.board.night` | ui | 7.89:1 | 7.89:1 | Pass |
| `color.whiteboard.pen.onDark.red` | `color.whiteboard.board.night` | ui | 7.25:1 | 7.25:1 | Pass |
| `color.whiteboard.pen.onDark.green` | `color.whiteboard.board.night` | ui | 11.52:1 | 11.52:1 | Pass |
| `color.whiteboard.pen.onDark.orange` | `color.whiteboard.board.night` | ui | 8.87:1 | 8.87:1 | Pass |
| `color.whiteboard.pen.onDark.purple` | `color.whiteboard.board.night` | ui | 7.59:1 | 7.59:1 | Pass |
| `color.state.error` | `color.action.destructive.default` | text | 5.49:1 | 8.03:1 | Pass |
| `color.state.error` | `color.action.destructive.hover` | text | 4.89:1 | 7.18:1 | Pass |
| `color.state.error` | `color.action.destructive.active` | text | 4.66:1 | 6.30:1 | Pass |
| `color.text.primary` | `color.state.infoBg` | text | 17.14:1 | 16.15:1 | Pass |
| `color.text.primary` | `color.state.successBg` | text | 17.40:1 | 15.33:1 | Pass |
| `color.text.primary` | `color.state.errorBg` | text | 17.12:1 | 16.30:1 | Pass |
| `color.state.success` | `color.state.infoBg` | text | 5.46:1 | 9.61:1 | Pass |
| `color.state.error` | `color.state.infoBg` | text | 5.50:1 | 7.96:1 | Pass |

Kind is `text` (needs 4.5:1), `large` (text 24px+ or 18.66px+ bold, needs 3:1), or `ui` (borders, icons, focus ring, needs 3:1). Ratios come from `check_sync.py`, never from estimation.

### 2.3 Color rules
- `color.accent` is used only for progress (quiz progress bar, "Question 2 of 5"), the current or selected item, key-term highlights in tutor replies, and badges. Why: one accent color keeps the screen calm (section 1).
- Text on an accent fill always uses `color.text.onAccent`. Why: ink fails on the light-mode accent, and white fails on the dark-mode accent.
- At most one primary button per screen or panel. All other buttons are secondary. Why: not given.
- `color.action.primary.default` fills primary buttons only, never chat bubbles, headers, or selected items. Why: not given.
- Errors and quiz results always show color, an icon, and text together, for example a cross icon with "Not quite, here's why", a check icon with "Correct". Why: color alone fails people with color blindness.
- Wrong answers use `color.state.error` on `color.state.errorBg`, never a stronger red. Why: mistakes should feel reassuring, not alarming (section 1).
- `color.border.subtle` and `color.border.default` are decorative and below 3:1 on purpose, so they are not in the 2.2 table. They are never the only visible edge of something the learner must see to use; use `color.border.strong` for those. Why: soft lines keep the screen calm, and must-see edges still pass.
- Disabled buttons, primary and secondary: no fill, `color.border.subtle` outline, `color.text.disabled` text. Why: clearly switched off, never mistaken for a secondary button.
- A whiteboard opens on `color.whiteboard.board.default`. The tutor draws with pen box 1, the learner with pen box 2. Why: familiar like a real classroom board, and the learner's blue keeps their marks apart from the tutor's.
- The pen menu and the board menu each show 6 color boxes plus a 7th box that opens a full color picker, like Excalidraw. Why: the most used colors are one tap away, any color is still possible.
- Pens follow the board, not the app mode: the white, yellow, blue, green, and pink boards use the `pen.onLight` set, the night board uses `pen.onDark`. On a picked board color, use the set whose tutor pen has the higher contrast with it. Why: pens stay visible on whatever board is chosen.
- With a picked pen or board color, the learner is responsible for visibility. Nothing changes automatically. Why: not given.
- The amber accent is never a pen color. Why: keeps the accent for the app's own highlights, and `#f08a4b` is 2.4:1 on the light board.

## 3. Typography

### 3.1 Font families
| Token | Value | Used for | Why |
|---|---|---|---|
| `font.family.body` | Atkinson Hyperlegible Next, Verdana, system-ui, sans-serif | All reading text, labels, buttons | The most accessible font for different people; Verdana is the fallback because it is also very legible and on almost every computer |
| `font.family.heading` | Atkinson Hyperlegible Next, Verdana, system-ui, sans-serif | All titles | Same font as the body, at bold weight: one font, fully consistent |
| `font.family.mono` | Atkinson Hyperlegible Mono, ui-monospace, Consolas, Menlo, monospace | Code, and numbers that must line up in columns | Matches the body font; the fallback is the device's own code font |

Font source: self-hosted font files bundled with the app, only the weights in 3.2. Why: works offline, nothing is sent to Google, suits a local-only app.

### 3.2 Scales
| Token | Value | Used for | Why |
|---|---|---|---|
| `font.size.xs` | 0.75rem | 12px. Badges and tiny counters only | Small steps suit dense screens like a session list |
| `font.size.sm` | 0.875rem | 14px. Small text, labels | Small steps suit dense screens like a session list |
| `font.size.md` | 1rem | 16px. Body text, buttons | The minimum set in section 1, fits more words on a phone |
| `font.size.lg` | 1.125rem | 18px. In the scale, no style uses it yet | Small steps suit dense screens like a session list |
| `font.size.xl` | 1.25rem | 20px. Card titles | Small steps suit dense screens like a session list |
| `font.size.2xl` | 1.5rem | 24px. Section titles, page titles on phones | Small steps suit dense screens like a session list |
| `font.size.3xl` | 2rem | 32px. Page titles | Small steps suit dense screens like a session list |
| `font.weight.regular` | 400 | Body, small text | Fewest weights, smallest files to load |
| `font.weight.bold` | 700 | Titles, labels, buttons, badges, emphasis | Fewest weights, smallest files to load |
| `font.lineHeight.normal` | 1.5 | Body, small, label | WCAG's recommended minimum |
| `font.lineHeight.tight` | 1.2 | Titles, buttons, badges | Not given |
| `font.letterSpacing.normal` | 0em | All text | Keep the font's own spacing, which is part of what makes it legible |

rem is used for every size. Why: sizes grow with the text size the person sets in their browser.

### 3.3 Text styles
| Token | Family | Size | Weight | Line height | Letter spacing | Used for | Why |
|---|---|---|---|---|---|---|---|
| `typography.pageTitle` | `font.family.heading` | `font.size.3xl` | `font.weight.bold` | `font.lineHeight.tight` | `font.letterSpacing.normal` | Page title | Not given |
| `typography.sectionTitle` | `font.family.heading` | `font.size.2xl` | `font.weight.bold` | `font.lineHeight.tight` | `font.letterSpacing.normal` | Section title, headings in tutor replies | Not given |
| `typography.cardTitle` | `font.family.heading` | `font.size.xl` | `font.weight.bold` | `font.lineHeight.tight` | `font.letterSpacing.normal` | Card title: quiz question, session name | Not given |
| `typography.body` | `font.family.body` | `font.size.md` | `font.weight.regular` | `font.lineHeight.normal` | `font.letterSpacing.normal` | Body text: chat messages, explanations | 16px minimum from section 1 |
| `typography.small` | `font.family.body` | `font.size.sm` | `font.weight.regular` | `font.lineHeight.normal` | `font.letterSpacing.normal` | Timestamps, captions, helper text | Not given |
| `typography.label` | `font.family.body` | `font.size.sm` | `font.weight.bold` | `font.lineHeight.normal` | `font.letterSpacing.normal` | Form labels, whiteboard tool names | Not given |
| `typography.button` | `font.family.body` | `font.size.md` | `font.weight.bold` | `font.lineHeight.tight` | `font.letterSpacing.normal` | Button text | Not given |
| `typography.buttonSmall` | `font.family.body` | `font.size.sm` | `font.weight.bold` | `font.lineHeight.tight` | `font.letterSpacing.normal` | Small button text | Not given |
| `typography.badge` | `font.family.body` | `font.size.xs` | `font.weight.bold` | `font.lineHeight.tight` | `font.letterSpacing.normal` | Badges, written in uppercase | The only uppercase and the only 12px text, so it always looks the same |

### 3.4 Typography rules
- Reading text (tutor replies, explanations) is at most 60 characters per line. Why: long lines are tiring, because the eye loses its place going back to the start of the next line.
- Bold is allowed for emphasis inside body text. Italic is never used. Why: italic is harder to read for some people, and it is one less font file.
- Uppercase is used only in `typography.badge`. Why: not given.
- `font.size.xs` (12px) is only for badges and tiny counters, never for sentences. Why: not given.
- On phones, the page title drops one step, from `font.size.3xl` to `font.size.2xl`. The phone width is set in section 6. Why: a 32px title takes too much space on a phone.
- `font.family.mono` is used for code blocks, inline code, and numbers that must line up in columns, such as quiz scores in a list. Why: every digit is the same width, so columns align.

## 4. Spacing

### 4.1 Spacing scale
| Token | Value | Why |
|---|---|---|
| `space.2xs` | 0.25rem | 4px. The base unit: a 4px base gives fine control |
| `space.xs` | 0.5rem | 8px. Step on the 4px scale |
| `space.sm` | 0.75rem | 12px. Step on the 4px scale |
| `space.md` | 1rem | 16px. Step on the 4px scale |
| `space.lg` | 1.5rem | 24px. Step on the 4px scale |
| `space.xl` | 2rem | 32px. Step on the 4px scale |
| `space.2xl` | 3rem | 48px. Step on the 4px scale |
| `space.3xl` | 4rem | 64px. Step on the 4px scale |

rem is used for every space. Why: space grows together with text when someone enlarges it in their browser.

### 4.2 Common gaps
| Token | Value | Used for | Why |
|---|---|---|---|
| `space.card.padding` | 1.5rem | Inside cards (24px, 16px on phones) | Room around content gives the calm feel |
| `space.section.gap` | 3rem | Between page sections (48px, 32px on phones) | A clear break between areas so nothing feels packed |
| `space.form.fieldGap` | 1rem | Between form fields (16px) | Fields still read as one form, 24 would scatter a short form |
| `space.form.labelGap` | 0.5rem | Label to input (8px) | Clearly belongs to its input without feeling cramped |
| `space.stack.default` | 1rem | Default gap between stacked items: chat messages, quiz options (16px) | Breathing room so a long reply does not run into the next message |
| `space.inline.default` | 0.5rem | Default gap between items in a row: icon and its text (8px) | Keeps an icon and its text visibly paired |

### 4.3 Spacing rules
- Only the 8 values in 4.1 are ever used. No value outside the scale, for any reason. Why: not given.
- On phones, `space.card.padding` drops to `space.md` (16px) and `space.section.gap` drops to `space.xl` (32px). Every other gap stays the same. The phone width is set in section 6. Why: keeps the calm feel on laptops without wasting narrow phone width.
- Screens use balanced density: comfortable, but lists and quizzes still show a good amount at once. Why: not given.

## 5. Radius, borders, shadows

### 5.1 Radius
| Token | Value | Used for | Why |
|---|---|---|---|
| `radius.xs` | 4px | Checkbox corners only | Keeps checkboxes clearly square, never confused with round radio buttons |
| `radius.sm` | 8px | Buttons, inputs (text boxes, chat input), the smallest inner corner | Rounded, soft shapes (section 1); gently rounded set chosen, why not given |
| `radius.md` | 12px | Cards (quiz, session), chat message bubbles | Rounded, soft shapes (section 1); gently rounded set chosen, why not given |
| `radius.lg` | 16px | Pop-ups (dialogs) | Rounded, soft shapes (section 1); gently rounded set chosen, why not given |
| `radius.full` | 9999px | Badges, tags, avatars | Fully round, the same in every set offered |

### 5.2 Borders
| Token | Value | Used for | Why |
|---|---|---|---|
| `border.width.default` | 1px | All normal borders | Not given |
| `border.width.emphasis` | 2px | Selected item, input with an error | Not given |
| `component.focusRing.width` | 2px | Thickness of the focus ring | Not given |
| `component.focusRing.offset` | 2px | Gap between the focus ring and the element | Not given |

### 5.3 Shadows
Shadows allowed: no

### 5.4 Radius, border, and shadow rules
- Corners by element: checkboxes use `radius.xs`; buttons and inputs use `radius.sm`; cards and chat bubbles use `radius.md`; pop-ups use `radius.lg`; badges, tags, and avatars use `radius.full`. Why: one corner size per kind of element keeps every screen consistent.
- A rounded thing inside another gets inner radius = outer radius minus the padding between them, never below `radius.sm`. Why: the curves look parallel.
- Cards and panels have a `border.width.default` border in `color.border.default`. Why: decorative edge, kept calm.
- Text inputs, the chat input, checkboxes, and quiz answer boxes have a `border.width.default` border in `color.border.strong`. Why: edges the learner must see to use pass 3:1.
- Dividers between chat messages and list items are `border.width.default` in `color.border.subtle`. Why: the faintest line, so lists stay calm.
- A selected quiz answer or the selected session gets a `border.width.emphasis` border in `color.accent`. Why: the selected item is an allowed accent use (2.3).
- An input with an error gets a `border.width.emphasis` border in `color.state.error`, plus an icon and message. Why: color, icon, and text for every error (2.3).
- Buttons have no border, except disabled buttons (`border.width.default` in `color.border.subtle`, see 2.3). Why: the fill shows the button, the outline shows it is switched off.
- Pop-ups and menus have a `border.width.default` border in `color.border.default`. Why: with no shadows, the border is what separates them from the page.
- The focus ring is `component.focusRing.width` thick in `color.focus.ring`, set `component.focusRing.offset` away from the element. Why: not given.
- No shadows anywhere, in light or dark mode. Floating things (menus, pop-ups, toasts) separate from the page with their border and `color.surface.raised`; dialogs also with `color.surface.overlay` behind them. Why: not given.

## 6. Layout

### 6.1 Grid
| Token | Value | Used for | Why |
|---|---|---|---|
| `layout.grid.columns` | 12 | Full pages: expanded quiz, settings | Not given |
| `layout.grid.gutter` | 1.5rem | Gap between grid columns (24px) | Not given |
| `layout.page.margin` | 1.5rem | Left and right screen edges, 640px and up (24px) | Not given |
| `layout.page.marginPhone` | 1rem | Left and right screen edges below 640px (16px) | Not given |
| `layout.panel.left` | 280px | Session list panel | Not given |
| `layout.panel.right` | 360px | Tools panel: whiteboard, quiz, artifacts | Not given |
| `layout.panel.rightWide` | 480px | Tools panel from `breakpoint.lg` up | Not given |
| `component.drawer.width` | 80% | Phone session menu, share of screen width | Not given |
| `component.bottomSheet.startHeight` | 33% | Phone tools sheet when it opens, share of screen height | Not given |
| `component.tapTarget.min` | 44px | Smallest tap area on touch screens, width and height | Not given |

### 6.2 Max content widths
| Token | Value | Used for | Why |
|---|---|---|---|
| `layout.maxWidth.content` | 1200px | Full pages: expanded quiz, settings | Not given |
| `layout.maxWidth.chat` | 720px | The chat column, including the input bar | Not given |
| `layout.maxWidth.form` | 400px | Forms, such as sign-in | Not given |

### 6.3 Breakpoints
| Token | Value | Used for | Why |
|---|---|---|---|
| `breakpoint.sm` | 640px | From here: chat plus the tools panel. Below: phone, one panel at a time | Not given |
| `breakpoint.md` | 1024px | From here: all three panels | Not given |
| `breakpoint.lg` | 1440px | From here: the tools panel widens to `layout.panel.rightWide` | Not given |

### 6.4 Z-index
| Token | Value | Used for | Why |
|---|---|---|---|
| `zIndex.sticky` | 100 | Chat input bar, top bar | Not given |
| `zIndex.dropdown` | 200 | Menus that drop down from a button | Not given |
| `zIndex.drawer` | 300 | Phone session menu, bottom sheet | Not given |
| `zIndex.modal` | 400 | Pop-up dialogs and their dim layer | Not given |
| `zIndex.toast` | 500 | Small temporary messages, such as "Saved" | Not given |
| `zIndex.tooltip` | 600 | Hint labels, always on top | Not given |

### 6.5 Layout rules
- The app is three panels: the session list on the left (`layout.panel.left`), the chat in the middle, tools on the right (`layout.panel.right`). The left and right panels can be closed. The chat is always visible and stops at `layout.maxWidth.chat`. Why: not given.
- The 12-column grid is used for full pages (expanded quiz, settings), which stop at `layout.maxWidth.content`. Why: not given.
- From `breakpoint.md` up: all three panels. From `breakpoint.lg` up, the tools panel is `layout.panel.rightWide`. Why: not given.
- From `breakpoint.sm` to below `breakpoint.md`: chat plus the tools panel. The session list is the menu button, as on phones. Why: not given.
- Below `breakpoint.sm` (phone), one panel at a time, and page margins are `layout.page.marginPhone`. Why: not given.
- Phone session list: a menu button. When open, it covers `component.drawer.width` of the screen width from the left. The chat stays visible and not dimmed in the remaining strip; tapping it closes the menu. Why: not given.
- Phone tools: a + button in the chat input opens a bottom sheet that starts at `component.bottomSheet.startHeight` of the screen height. Two stops: the start height and full screen. Dragging below the start closes it. Why: not given.
- Every tappable thing has a tap area of at least `component.tapTarget.min` by `component.tapTarget.min`, even when the visible icon is smaller. Why: not given.
- Horizontal scrolling is allowed only on the whiteboard, which pans in every direction. Everything else wraps or stacks, including wide code blocks and tables in tutor replies. Why: not given.

## 7. Components

Component list: button, icon button, link, badge, tooltip, text input, checkbox, radio, chat input, chat message, thinking indicator, quiz question card, answer option, progress bar, result feedback, whiteboard toolbar, color swatch picker, session list item, side panel, drawer, bottom sheet, tabs, modal, dropdown menu, toast, alert, empty state, loading skeleton or spinner, card, avatar, top bar, comment pin.

Still to define: TBD (end-of-quiz summary, the "See results" screen)

### Button
Purpose: triggers an action, such as Send, Submit, or Start quiz. Not for going to another page or place: use a link.

Variants:
| Variant | When to use | Why |
|---|---|---|
| primary | The one main action on a screen or panel (at most one, see 2.3) | One clear next step |
| secondary | Every other action: Skip, Cancel | Not given |
| ghost | Low-key actions: Show more | Not given |
| destructive | Actions that delete something: Delete session | Soft error colors, never a harsh red (section 1) |

Button tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.button.height.md` | 44px | Medium button height | Matches the 44px tap target |
| `component.button.height.sm` | 36px | Small button visible height, with a 44px tap area | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md (default) | `component.button.height.md` | 0 `space.md` | `typography.button` | Not given |
| sm | `component.button.height.sm` | 0 `space.sm` | `typography.buttonSmall` | Not given |

States (all variants, shared):
| State | What changes | Tokens |
|---|---|---|
| focus | 2px ring outside the button, 2px away | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| disabled | No fill, outline, faded text, not clickable | `color.action.primary.disabled`, `border.width.default`, `color.border.subtle`, `color.text.disabled` |
| loading | Fill unchanged, a spinner in the variant's text color replaces the text, width kept, clicks blocked | the variant's default tokens |
| error | n/a: a button has no error state; errors show on the input or in an alert | n/a |
| empty | n/a: a button always has a label | n/a |

States (variant: primary):
| State | What changes | Tokens |
|---|---|---|
| default | Ink fill, warm white text | `color.action.primary.default`, `color.text.onAction` |
| hover | Fill steps lighter | `color.action.primary.hover` |
| active | Fill steps lighter again | `color.action.primary.active` |

States (variant: secondary):
| State | What changes | Tokens |
|---|---|---|
| default | Soft fill, primary text | `color.action.secondary.default`, `color.text.primary` |
| hover | Fill steps darker | `color.action.secondary.hover` |
| active | Fill steps darker again | `color.action.secondary.active` |

States (variant: ghost):
| State | What changes | Tokens |
|---|---|---|
| default | No fill, primary text | `color.text.primary` |
| hover | Gains the secondary fill | `color.action.secondary.default` |
| active | Gains the secondary hover fill | `color.action.secondary.hover` |

States (variant: destructive):
| State | What changes | Tokens |
|---|---|---|
| default | Soft error fill, error text | `color.action.destructive.default`, `color.state.error` |
| hover | Fill steps deeper | `color.action.destructive.hover` |
| active | Fill steps deeper again | `color.action.destructive.active` |

#### Button rules
- A destructive button always opens a confirm dialog ("Delete this session? This can't be undone.") before anything is deleted. Why: not given.
- Button text is a verb that says what happens, such as "Start quiz" or "Delete session", never "OK" or "Yes". Why: not given.
- Loading keeps the button's width and blocks clicks. Why: not given.

### Icon button
Purpose: an action shown as an icon with no visible text, such as close, menu, the + tools button, or Send. Every icon button has a screen reader name, such as "Close" or "Open tools". No tooltip.

Variants:
| Variant | When to use | Why |
|---|---|---|
| ghost | Most icon buttons: close, menu, + tools | Not given |
| primary | Only Send in the chat input, and Stop in its place while the tutor replies | The main action in the chat |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md (default) | `component.button.height.md`, square | n/a: icon centered, size set in section 9 | n/a: no text | Same heights as buttons |
| sm | `component.button.height.sm`, square, 44px tap area | n/a: icon centered, size set in section 9 | n/a: no text | Same heights as buttons |

States (all variants):
| State | What changes | Tokens |
|---|---|---|
| default | Same as the button variant with the same name; the icon takes the text color | see Button |
| hover | Same as the button variant | see Button |
| active | Same as the button variant | see Button |
| focus | Same as Button | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| disabled | Same as Button | `color.action.primary.disabled`, `border.width.default`, `color.border.subtle`, `color.text.disabled` |
| loading | A spinner replaces the icon, width kept, clicks blocked | the variant's default tokens |
| error | n/a: same reason as Button | n/a |
| empty | n/a: always has an icon and a screen reader name | n/a |

#### Icon button rules
- Every icon button has a screen reader name that says what it does. Why: without visible text, screen reader users would hear nothing useful.
- Primary icon buttons are used only for Send, and for Stop, which takes Send's place while the tutor replies. Why: not given.

### Link
Purpose: goes to another page or place, such as a session, a page, or a source the tutor cites. Not for actions: use a button.

Variants:
| Variant | When to use | Why |
|---|---|---|
| inline | Links inside text | Calmest option, keeps a single accent (2.3) |
| external | Links that leave Polaris | The learner knows they are leaving the app |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| inherit | n/a: flows with the text | n/a | the surrounding text style | A link matches the text it sits in |

States (all variants):
| State | What changes | Tokens |
|---|---|---|
| default | Ink, underlined with a 1px line | `color.text.link`, `border.width.default` |
| hover | Underline thickens to 2px | `border.width.emphasis` |
| active | TBD (same as hover, or thicker underline plus `color.text.secondary`) | TBD |
| focus | Focus ring around the link | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| disabled | n/a: a link that cannot be used is shown as plain text instead | n/a |
| loading | n/a: the page it opens shows its own loading | n/a |
| error | n/a: a broken destination shows its own error | n/a |
| empty | n/a: a link always has text | n/a |

#### Link rules
- Visited links look the same as unvisited ones. Why: in an app, "visited" means little.
- External links show an "opens outside" icon after the text (icon set in section 9) and open in a new tab. Why: the learner knows they are leaving Polaris and does not lose their session.

### Badge
Purpose: a small pill label, such as "NEW", or a count. Not interactive. Never a dot without text.

Variants:
| Variant | When to use | Why |
|---|---|---|
| accent | Something that needs attention: NEW | Badges are an allowed accent use (2.3) |
| neutral | Quiet labels or counts: Draft, 3 | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | n/a: set by text and padding, about 22px | `space.2xs` `space.xs` | `typography.badge` | Not given |

States (variant: accent):
| State | What changes | Tokens |
|---|---|---|
| default | Amber fill, text on accent, fully round | `color.accent`, `color.text.onAccent`, `radius.full` |
| hover | n/a: not interactive | n/a |
| active | n/a: not interactive | n/a |
| focus | n/a: not interactive, never receives focus | n/a |
| disabled | n/a: not interactive | n/a |
| loading | n/a: shown only once its content is known | n/a |
| error | n/a: errors use an alert, not a badge | n/a |
| empty | n/a: a badge with nothing to say is not shown | n/a |

States (variant: neutral):
| State | What changes | Tokens |
|---|---|---|
| default | Subtle fill, secondary text, fully round | `color.bg.subtle`, `color.text.secondary`, `radius.full` |
| hover | n/a: not interactive | n/a |
| active | n/a: not interactive | n/a |
| focus | n/a: not interactive, never receives focus | n/a |
| disabled | n/a: not interactive | n/a |
| loading | n/a: shown only once its content is known | n/a |
| error | n/a: errors use an alert, not a badge | n/a |
| empty | n/a: a badge with nothing to say is not shown | n/a |

#### Badge rules
- Badges always contain text. Never use a dot without text. Why: dots look like generic AI design.

### Tooltip
Purpose: kept for a future use case. Icon buttons do not use it (see Icon button). Its look is not decided yet.

Variants:
| Variant | When to use | Why |
|---|---|---|
| TBD | TBD | TBD |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD |

States (variant: TBD):
| State | What changes | Tokens |
|---|---|---|
| default | TBD (fill color is TBD) | TBD |
| hover | TBD | TBD |
| active | TBD | TBD |
| focus | TBD | TBD |
| disabled | TBD | TBD |
| loading | TBD | TBD |
| error | TBD | TBD |
| empty | TBD | TBD |

#### Tooltip rules
- TBD

### Text input
Purpose: a single line of typed text, such as email or password on sign-in. Not for chat messages: use the chat input.

Variants:
| Variant | When to use | Why |
|---|---|---|
| text | Any single-line field: email, name | Not given |
| password | Passwords: adds a show/hide icon button (ghost, sm) inside the field, on the right | Typing passwords blind on a phone causes typos; checking helps stressed or tired learners |

Text input tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.input.height` | 44px | Text input height | Matches the 44px tap target and button height |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | `component.input.height` | 0 `space.md` | `typography.body` | 16px side padding lines up with button text; 16px text stops iPhones zooming in |

States (all variants):
| State | What changes | Tokens |
|---|---|---|
| default | Surface fill, 1px strong border, label above, optional placeholder | `color.surface.default`, `border.width.default`, `color.border.strong`, `radius.sm`, `color.text.primary`, `color.text.muted` |
| hover | Border darkens | `color.text.secondary` |
| active | n/a: typing in the field is the focus state | n/a |
| focus | Focus ring around the field, border unchanged | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| disabled | Subtle fill, subtle border, faded text, cannot type | `color.bg.subtle`, `color.border.subtle`, `color.text.disabled` |
| loading | n/a: a text input does not wait on anything | n/a |
| error | 2px error border; under the field, an error icon and message replace the help text | `border.width.emphasis`, `color.state.error`, `typography.small` |
| empty | Shows the placeholder if it has one, otherwise blank | `color.text.muted` |

#### Text input rules
- The label is always visible above the field in `typography.label`, `space.form.labelGap` away. A placeholder never replaces the label. Why: a placeholder disappears when typing, and people forget what the field was for.
- Placeholders are only for examples, such as "name@example.com". Why: not given.
- Help text sits under the field in `typography.small` and `color.text.secondary`. Why: not given.

### Checkbox and radio
Purpose: checkbox picks any number of options; radio picks exactly one from a list. Used in forms and settings. Quiz answers use the answer option component.

Variants:
| Variant | When to use | Why |
|---|---|---|
| checkbox | Pick any number, or a single yes/no like "Remember me" | Not given |
| radio | Pick exactly one from a list | Not given |

Checkbox and radio tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.checkbox.size` | 24px | Visible box and circle size, inside a 44px tap area | Easier to see and hit for tired eyes and shaky thumbs |
| `component.radio.markSize` | 10px | The inner circle of a selected radio | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | `component.checkbox.size` | `space.inline.default` between the box and its label | `typography.body` for the label | Not given |

States (all variants):
| State | What changes | Tokens |
|---|---|---|
| default | Unchecked: surface fill, 1px strong border (checkbox corners `radius.xs`, radio `radius.full`). Checked: amber fill, check mark (checkbox) or inner circle (radio) in text on accent | `color.surface.default`, `border.width.default`, `color.border.strong`, `radius.xs`, `radius.full`, `color.accent`, `color.text.onAccent` |
| hover | Unchecked: border darkens. Checked: no change | `color.text.secondary` |
| active | n/a: pressing toggles it straight to the other state | n/a |
| focus | Focus ring around the box or circle | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| disabled | Subtle fill, subtle border, the mark and label faded | `color.bg.subtle`, `color.border.subtle`, `color.text.disabled` |
| loading | n/a: toggling is instant | n/a |
| error | The error icon and message below the group, such as "Pick one answer" | `color.state.error`, `typography.small` |
| empty | n/a: unchecked is the default state | n/a |

#### Checkbox and radio rules
- Chosen always means an amber fill with a mark in `color.text.onAccent`, for both checkbox and radio. Why: one rule for both, and a filled box is easy to tell apart from an empty one.
- The label is tappable and part of the 44px tap area. Why: a 24px box alone is a small target.

### Chat input
Purpose: where the learner types to the tutor. One box holding the + tools button, the text, and Send. Not for other forms: use the text input.

Variants:
| Variant | When to use | Why |
|---|---|---|
| default | The only variant: bottom of every chat | Familiar pattern from other chat apps, one clear place to look |

Chat input tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.chatInput.maxLines` | 6 | Lines the box grows to before scrolling inside | Long questions stay readable, the last reply stays visible on a phone |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | Grows from one line to `component.chatInput.maxLines` lines; buttons are `component.button.height.md` | `space.2xs` inside the box; the bar around it has `space.md` | `typography.body` | 16px text stops iPhones zooming in |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Bar in subtle fill; box with surface fill, 1px strong border, 8px corners; + (ghost icon button) left, Send (primary icon button) right | `color.bg.subtle`, `color.surface.default`, `border.width.default`, `color.border.strong`, `radius.sm` |
| hover | Box border darkens | `color.text.secondary` |
| active | n/a: typing is the focus state | n/a |
| focus | Focus ring around the whole box while typing | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| disabled | Subtle fill, subtle border, faded text, cannot type | `color.bg.subtle`, `color.border.subtle`, `color.text.disabled` |
| loading | While the tutor replies, Send becomes Stop (same spot, size, and style); the learner can still type | `color.action.primary.default`, `color.text.onAction` |
| error | A message failed to send: the text stays in the box; under it, an error icon and message | `color.state.error`, `typography.small` |
| empty | Placeholder shows; Send is disabled | `color.text.muted` |

#### Chat input rules
- On a laptop, Enter sends and Shift+Enter makes a new line. On a phone, Enter makes a new line and only Send sends. Why: matches what people expect; phone keyboards have no easy Shift.
- While the tutor replies, Send becomes Stop. Stopping keeps what the tutor wrote so far. Why: honest, and puts the learner in control of a long reply.
- The input bar sticks to the bottom of the chat (`zIndex.sticky`). Why: not given.

### Chat message
Purpose: one turn in the chat, from the learner or the tutor.

Variants:
| Variant | When to use | Why |
|---|---|---|
| learner | The learner's messages: a bubble on the right | The bubble keeps it obvious who said what |
| tutor | Tutor replies: plain full-width text on the page, with the Polaris star icon and "Polaris" above | Long structured replies read best without a bubble; always clear who is speaking |

Chat message tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.chatMessage.learnerMaxWidth` | 80% | Widest a learner bubble gets, as a share of the chat column | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| learner | n/a: fits its text | `space.sm` `space.md` inside the bubble | `typography.body` | Not given |
| tutor | n/a: fits its text | none; the name row sits `space.xs` above the text | `typography.body`; name in `typography.label`; headings in `typography.sectionTitle` | Not given |

States (variant: learner):
| State | What changes | Tokens |
|---|---|---|
| default | Surface fill, 1px default border, 12px corners, right aligned | `color.surface.default`, `border.width.default`, `color.border.default`, `radius.md`, `color.text.primary` |
| hover | Timestamp appears under the bubble (tap on phones) | `typography.small`, `color.text.secondary` |
| active | n/a: a message is not pressable | n/a |
| focus | n/a: the message is not focusable; its timestamp shows when it is tapped | n/a |
| disabled | n/a: messages cannot be disabled | n/a |
| loading | n/a: shown at once when sent | n/a |
| error | Failed to send: shown by the chat input (see Chat input) | see Chat input |
| empty | n/a: an empty message cannot be sent | n/a |

States (variant: tutor):
| State | What changes | Tokens |
|---|---|---|
| default | Text on the page, name row above, Copy and Try again (ghost icon buttons, sm) below | `color.text.primary`, `typography.label` |
| hover | Timestamp appears next to the name (tap on phones) | `typography.small`, `color.text.secondary` |
| active | n/a: a message is not pressable | n/a |
| focus | n/a: Copy and Try again take focus, not the message | n/a |
| disabled | n/a: messages cannot be disabled | n/a |
| loading | Before the first words: the thinking indicator. Then the text appears as it arrives | see Thinking indicator |
| error | The reply failed: error icon and message where the reply would be, with a Try again button (secondary) | `color.state.error`, `typography.small` |
| empty | n/a: a reply always has content, or it shows the error state | n/a |

#### Chat message rules
- Messages are `space.stack.default` apart. Why: breathing room so a long reply does not run into the next message.
- Tutor replies follow the reading width rule (60 characters) and the structure rule: headings, numbered steps, short paragraphs (section 1). Why: Guiding.
- Copy and Try again are always visible under a finished tutor reply, never hidden behind hover. Why: phones have no hover.

### Thinking indicator
Purpose: shows that the tutor is working and says what it is doing, before its reply starts. Never bouncing dots.

Variants:
| Variant | When to use | Why |
|---|---|---|
| default | Between the learner sending and the first words of the reply | Honest about what is happening, never a frozen screen (section 1) |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | n/a: one line | none; star icon `space.inline.default` before the text | `typography.small` | Not given |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Star icon gently pulses (motion set in section 8) next to status text: Thinking, Drawing on the whiteboard, Writing a quiz | `color.text.secondary`, `color.accent` |
| hover | n/a: not interactive | n/a |
| active | n/a: not interactive | n/a |
| focus | n/a: not interactive; screen readers hear the status text | n/a |
| disabled | n/a: not interactive | n/a |
| loading | n/a: it is itself the loading state | n/a |
| error | n/a: a failed reply uses the tutor message error state | n/a |
| empty | n/a: always has status text | n/a |

#### Thinking indicator rules
- The status text names the real activity, never a fake one. Why: Trustworthy, honest about what is happening.
- Screen readers announce each status change. Why: not given.
- The star icon uses `color.accent`, counted as a progress use (2.3). Why: not given.

### Quiz question card
Purpose: holds one quiz question: progress at the top, the question, the answer options, the result feedback, and one primary button. Lives in the chat, the tools panel, or its own page.

Variants:
| Variant | When to use | Why |
|---|---|---|
| default | Every quiz question, one at a time | One step at a time keeps the learner focused |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | n/a: fits its content | `space.card.padding` | question in `typography.cardTitle` | Not given |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Card: surface fill, 1px default border, 12px corners. Progress bar, question, options `space.stack.default` apart, "Check answer" primary button, disabled until an answer is picked | `color.surface.default`, `border.width.default`, `color.border.default`, `radius.md` |
| hover | n/a: the card itself is not interactive | n/a |
| active | n/a: the card itself is not interactive | n/a |
| focus | n/a: options and the button take focus | n/a |
| disabled | n/a: after checking, the options lock instead (see Answer option) | n/a |
| loading | While the quiz is being written: the thinking indicator ("Writing a quiz") in place of the card | see Thinking indicator |
| error | The quiz could not load: error icon and message in the card, with a Try again button (secondary) | `color.state.error`, `typography.small` |
| empty | n/a: a quiz always has at least one question | n/a |

#### Quiz question card rules
- One question at a time. After "Check answer", the result feedback appears and the button becomes "Next question" ("See results" on the last one). Why: one step at a time keeps the learner focused.
- The correct answer is revealed right after checking, with the explanation. Why: the score honestly matches the stored answer key on the first try, and the "here's why" teaches immediately.

### Answer option
Purpose: one answer in a quiz question: a full-width row with a radio (one correct answer) or checkbox (several), the whole row tappable.

Variants:
| Variant | When to use | Why |
|---|---|---|
| single | Questions with one correct answer: radio inside | Not given |
| multiple | Questions with several correct answers: checkbox inside | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | At least `component.tapTarget.min`, grows with its text | `space.md` | `typography.body` | A big target is easy on a phone |

States (all variants):
| State | What changes | Tokens |
|---|---|---|
| default | Surface fill, 1px strong border, 8px corners | `color.surface.default`, `border.width.default`, `color.border.strong`, `radius.sm` |
| hover | Border darkens | `color.text.secondary` |
| active | n/a: pressing selects it (see selected) | n/a |
| focus | Focus ring around the row | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| selected | 2px accent border, radio or checkbox filled | `border.width.emphasis`, `color.accent` |
| disabled | After checking: locked, not clickable, look unchanged apart from the marks below | n/a |
| correct | After checking, the correct answer: 2px success border, success background, check icon and "Correct answer" | `border.width.emphasis`, `color.state.success`, `color.state.successBg`, `typography.small` |
| incorrect | After checking, the learner's wrong pick: 2px error border, soft error background, cross icon and "Your answer" | `border.width.emphasis`, `color.state.error`, `color.state.errorBg`, `typography.small` |
| loading | n/a: the options appear with the card | n/a |
| error | n/a: "Check answer" is disabled until something is picked, so there is no "nothing picked" error | n/a |
| empty | n/a: an option always has text | n/a |

#### Answer option rules
- Right and wrong are always shown with color, icon, and text together. Why: color alone fails people with color blindness (2.3).

### Progress bar
Purpose: shows how far through something the learner is, such as a quiz. Always with text above it.

Variants:
| Variant | When to use | Why |
|---|---|---|
| default | Quiz progress | Visible progress at a glance (section 1, Guiding) |

Progress bar tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.progress.height` | 8px | Bar height | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | `component.progress.height` | text `space.xs` above the bar | `typography.small` in `color.text.secondary`: "Question 2 of 5" | The text gives screen readers the same information |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Subtle track, amber filled part, fully round | `color.bg.subtle`, `color.accent`, `radius.full` |
| hover | n/a: not interactive | n/a |
| active | n/a: not interactive | n/a |
| focus | n/a: not interactive; screen readers read the text | n/a |
| disabled | n/a: not interactive | n/a |
| loading | n/a: shown once the number of questions is known | n/a |
| error | n/a: errors show in the quiz card | n/a |
| empty | At the start: "Question 1 of 5" with an empty track | `color.bg.subtle` |

### Result feedback
Purpose: after checking an answer, says right or wrong and explains why. Same calm box for both.

Variants:
| Variant | When to use | Why |
|---|---|---|
| correct | The learner was right: check icon and "Correct" in success color, then the explanation | Not given |
| incorrect | The learner was wrong: cross icon and "Not quite, here's why" in error color, then the explanation | Mistakes feel reassuring, not alarming (section 1) |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | n/a: fits its text | `space.md` | headline in `typography.label`, explanation in `typography.body` | Not given |

States (all variants):
| State | What changes | Tokens |
|---|---|---|
| default | Soft info background, 12px corners; headline in the outcome color; explanation in primary text | `color.state.infoBg`, `radius.md`, `color.state.success`, `color.state.error`, `color.text.primary` |
| hover | n/a: not interactive | n/a |
| active | n/a: not interactive | n/a |
| focus | n/a: not interactive; screen readers announce it when it appears | n/a |
| disabled | n/a: not interactive | n/a |
| loading | n/a: appears with the check result | n/a |
| error | n/a: a failed check uses the quiz card error state | n/a |
| empty | n/a: always has a headline and an explanation | n/a |

#### Result feedback rules
- Both variants use the soft info background, so a wrong answer never turns the screen red. Why: Reassuring (section 1).

### Whiteboard toolbar
Purpose: the tools the learner uses to draw on the whiteboard. The tutor draws through the app, not the toolbar.

Variants:
| Variant | When to use | Why |
|---|---|---|
| laptop | 640px and up: floating bar at the top center of the board | Familiar from Excalidraw |
| phone | Below 640px: the same bar at the bottom of the board | In thumb reach |

Whiteboard tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.whiteboard.pen.thin` | 2px | Thin pen | Not given |
| `component.whiteboard.pen.medium` | 4px | Medium pen | Not given |
| `component.whiteboard.pen.thick` | 8px | Thick pen | Not given |

Tools, in order: select and move, pen, eraser, shapes (one button opening line, arrow, rectangle, circle), text, comment, then undo, redo, pan and zoom, and a "more" menu holding Clear board.

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | Tools are icon buttons, `component.button.height.md` | `space.2xs` around the tools | n/a: icons only, each with a screen reader name | Full-size tools for touch |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Bar: raised surface, 1px default border, 12px corners, no shadow; tools are ghost icon buttons | `color.surface.raised`, `border.width.default`, `color.border.default`, `radius.md` |
| hover | The tool under the pointer: ghost hover | see Icon button |
| active | The tool being pressed: ghost active | see Icon button |
| focus | Focus ring on the tool | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| selected | The tool in use: amber fill, icon in text on accent | `color.accent`, `color.text.onAccent` |
| disabled | Undo or redo with nothing to undo or redo: disabled look | see Icon button |
| loading | n/a: tools switch instantly | n/a |
| error | n/a: errors show in an alert | n/a |
| empty | n/a: the bar always has its tools | n/a |

#### Whiteboard toolbar rules
- Shapes share one button, and Clear board sits in the "more" menu. Why: fewer buttons on the bar, and Clear board is never tapped by accident.
- Clear board is a destructive action: it opens a confirm dialog first. Why: drawings cannot be recovered.
- Board text uses the body font at `font.size.2xl` or `font.size.3xl` only. Why: at 24px and up WCAG needs 3:1, and every pen passes on every board.

### Color swatch picker
Purpose: picks a pen color or a board color: 6 color boxes plus a 7th box that opens a full color picker.

Variants:
| Variant | When to use | Why |
|---|---|---|
| pen | Pen colors: the `pen.onLight` or `pen.onDark` set, following the board (2.3) | Pens stay visible on the board |
| board | Board colors: the 6 board boxes | A few soft tints give variety without clutter |

Swatch tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.swatch.size` | 32px | Visible color box, inside a 44px tap area | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | `component.swatch.size`, square | boxes `space.sm` apart, so each has a 44px tap area | n/a: each box has a screen reader name, such as "Blue" | Not given |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Color box, 8px corners, 1px default border so pale colors show on a pale surface | `radius.sm`, `border.width.default`, `color.border.default` |
| hover | Border darkens | `color.text.secondary` |
| active | n/a: pressing selects it | n/a |
| focus | Focus ring | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| selected | 2px ring in the primary text color, 2px away: ink in light mode, warm white in dark mode | `border.width.emphasis`, `color.text.primary` |
| disabled | n/a: colors are always available | n/a |
| loading | n/a: instant | n/a |
| error | n/a: any picked color is accepted (the learner is responsible, 2.3) | n/a |
| empty | The 7th box shows a + icon until a custom color is picked, then shows that color | `color.text.primary` |

#### Color swatch picker rules
- The 7th box never shows a rainbow gradient. Why: no flashy gradients (section 1, Trustworthy).
- The selected ring uses `color.text.primary`, not the accent. Why: it shows on both toolbar surfaces and does not clash with the orange pen.

### Session list item
Purpose: one session in the left panel. Tapping it opens that session.

Variants:
| Variant | When to use | Why |
|---|---|---|
| default | Every session in the list | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | At least `component.tapTarget.min` | `space.sm` `space.md` | title in `typography.body` (one line, cut with "..."), date in `typography.small` | Title and date only keeps the list calm |

States:
| State | What changes | Tokens |
|---|---|---|
| default | No fill, 8px corners; title, date in secondary text; more button (ghost icon button, sm) on the right | `radius.sm`, `color.text.primary`, `color.text.secondary` |
| hover | Gains the secondary fill | `color.action.secondary.default` |
| active | Gains the secondary hover fill | `color.action.secondary.hover` |
| focus | Focus ring | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| selected | The open session: surface fill and a 2px accent border | `color.surface.default`, `border.width.emphasis`, `color.accent` |
| disabled | n/a: a session can always be opened | n/a |
| loading | While the list loads: loading skeleton rows | see Loading skeleton or spinner |
| error | The list could not load: an alert in the panel with Try again | see Alert |
| empty | No sessions yet: the empty state in the panel | see Empty state |

#### Session list item rules
- Sessions are grouped under "Today", "Yesterday", and "Earlier", newest first. Group names in `typography.label` and `color.text.secondary`. Why: easy to find a session.
- The more button is always visible and opens a menu with Rename and Delete (Delete is destructive and confirms). Why: phones have no hover.

### Side panel
Purpose: the left session list and the right tools panel on laptops. On phones they become the drawer and the bottom sheet.

Variants:
| Variant | When to use | Why |
|---|---|---|
| left | The session list, `layout.panel.left` wide | Not given |
| right | The tools panel, `layout.panel.right` (or `layout.panel.rightWide`) wide, with tabs at the top | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | Full height | `space.md` | header title in `typography.label` | Not given |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Subtle background; a 1px subtle line on the chat side; header with title and a close button (ghost icon button, sm) | `color.bg.subtle`, `border.width.default`, `color.border.subtle` |
| hover | n/a: the panel itself is not interactive | n/a |
| active | n/a: the panel itself is not interactive | n/a |
| focus | n/a: its contents take focus | n/a |
| disabled | n/a: a panel is either open or closed | n/a |
| loading | n/a: its content shows its own loading | n/a |
| error | n/a: its content shows its own error | n/a |
| empty | n/a: its content shows its own empty state | n/a |

#### Side panel rules
- Closing a panel gives its space to the chat. A button in the top bar opens it again. Why: not given.

### Tabs
Purpose: switches between views in the same place, such as Whiteboard, Quiz, and Artifacts in the tools panel.

Variants:
| Variant | When to use | Why |
|---|---|---|
| underline | All tabs | Calmer than pills; the selected tab is an allowed accent use (2.3) |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | `component.tapTarget.min` | 0 `space.md` | `typography.label` | Not given |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Secondary text; a 1px subtle line under the whole row of tabs | `color.text.secondary`, `border.width.default`, `color.border.subtle` |
| hover | Text becomes primary | `color.text.primary` |
| active | n/a: pressing selects it | n/a |
| focus | Focus ring | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| selected | Primary text and a 2px amber underline | `color.text.primary`, `border.width.emphasis`, `color.accent` |
| disabled | Faded text, cannot be selected | `color.text.disabled` |
| loading | n/a: the content below shows its own loading | n/a |
| error | n/a: the content below shows its own error | n/a |
| empty | n/a: there are always at least two tabs | n/a |

### Comment pin
Purpose: a note pinned to a spot on the whiteboard, by the learner or the tutor. Tapping it opens a small card with the comment.

Variants:
| Variant | When to use | Why |
|---|---|---|
| default | All comments, from anyone | The same pin shows on every board color; the card says who wrote it |

Comment pin tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.commentPin.size` | 32px | Comment pin on the whiteboard, inside a 44px tap area | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | `component.commentPin.size`, round | n/a: speech-bubble icon centered | Card: author in `typography.label` ("You" or "Polaris"), comment in `typography.body` | Not given |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Raised surface, 1px strong border, fully round, icon in primary text | `color.surface.raised`, `border.width.default`, `color.border.strong`, `radius.full`, `color.text.primary` |
| hover | Border darkens | `color.text.secondary` |
| active | n/a: pressing opens the card | n/a |
| focus | Focus ring | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| selected | The card is open: 2px accent border on the pin. The card is a raised surface with a 1px default border, 12px corners, `space.sm` padding, at most `layout.panel.left` wide | `border.width.emphasis`, `color.accent`, `color.surface.raised`, `color.border.default`, `radius.md` |
| disabled | n/a: comments can always be opened | n/a |
| loading | n/a: shown once saved | n/a |
| error | Could not save: the error icon and message in the card | `color.state.error`, `typography.small` |
| empty | n/a: an empty comment cannot be saved | n/a |

### Drawer
Purpose: the phone session list (below 640px), sliding in from the left.

Variants:
| Variant | When to use | Why |
|---|---|---|
| left | The session list on phones | Set in section 6 |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | Full height, `component.drawer.width` wide | `space.md` | header title in `typography.label` | Set in section 6 |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Open: subtle background like the side panel, a 1px default border on its right edge, above the chat, chat not dimmed | `color.bg.subtle`, `border.width.default`, `color.border.default`, `zIndex.drawer` |
| hover | n/a: the drawer itself is not interactive | n/a |
| active | n/a: the drawer itself is not interactive | n/a |
| focus | Focus moves into the drawer when it opens and back to the menu button when it closes | n/a |
| disabled | n/a: a drawer is either open or closed | n/a |
| loading | n/a: its content shows its own loading | n/a |
| error | n/a: its content shows its own error | n/a |
| empty | n/a: its content shows its own empty state | n/a |

#### Drawer rules
- Closes by swiping left, tapping the chat strip, or its close button (ghost icon button). Why: every drag has a tap alternative.

### Bottom sheet
Purpose: the phone tools panel (below 640px), sliding up from the bottom after the + button in the chat input.

Variants:
| Variant | When to use | Why |
|---|---|---|
| default | Tools on phones | Set in section 6 |

Bottom sheet tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.bottomSheet.handleWidth` | 32px | Grab handle width | Shows the sheet can be dragged |
| `component.bottomSheet.handleHeight` | 4px | Grab handle height | Shows the sheet can be dragged |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | Starts at `component.bottomSheet.startHeight`, stops at full screen | `space.md` | n/a: its content sets the text | Set in section 6 |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Raised surface, top corners 16px, 1px default border on the top edge, grab handle centered at the top in the strong border color, fully round | `color.surface.raised`, `radius.lg`, `border.width.default`, `color.border.default`, `color.border.strong`, `radius.full`, `zIndex.drawer` |
| hover | n/a: the sheet itself is not interactive | n/a |
| active | While dragged, it follows the finger and settles at the nearest stop | n/a |
| focus | Focus moves into the sheet when it opens and back to the + button when it closes; the handle is focusable | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| disabled | n/a: a sheet is either open or closed | n/a |
| loading | n/a: its content shows its own loading | n/a |
| error | n/a: its content shows its own error | n/a |
| empty | n/a: its content shows its own empty state | n/a |

#### Bottom sheet rules
- Tapping the handle switches between the start height and full screen. Swiping down below the start height, or the close button, closes it. Why: every drag has a tap alternative (WCAG).

### Modal
Purpose: a pop-up dialog that needs an answer before going on, such as "Delete this session?".

Variants:
| Variant | When to use | Why |
|---|---|---|
| default | Questions and short forms | Not given |
| confirm | Before a destructive action: the destructive button is the main action | A destructive action always confirms (Button rules) |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | Fits its content, at most `layout.maxWidth.form` wide; on phones `layout.page.marginPhone` from the edges | `space.card.padding` | title in `typography.cardTitle`, text in `typography.body` | Same width as forms |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Centered; raised surface, 1px default border, 16px corners, no shadow; the dim layer behind | `color.surface.raised`, `border.width.default`, `color.border.default`, `radius.lg`, `color.surface.overlay`, `zIndex.modal` |
| hover | n/a: the dialog itself is not interactive | n/a |
| active | n/a: the dialog itself is not interactive | n/a |
| focus | Focus moves into the dialog and stays inside until it closes, then returns to what opened it | n/a |
| disabled | n/a: a dialog is either open or closed | n/a |
| loading | Its main button shows its loading state | see Button |
| error | An alert inside the dialog, above the buttons | see Alert |
| empty | n/a: a dialog always has a title and text | n/a |

#### Modal rules
- Closing by the close button, Escape, or tapping the dim layer always means cancel. Why: closing is never a hidden "yes".
- Laptop: the main button on the right, secondary to its left, `space.inline.default` apart. Phone: stacked full width, the main button on top. Why: not given.

### Dropdown menu
Purpose: a short list of actions that opens from a button, such as the session's Rename and Delete.

Variants:
| Variant | When to use | Why |
|---|---|---|
| default | All menus | Not given |

Dropdown tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.menu.minWidth` | 200px | Narrowest a menu gets | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | Rows `component.tapTarget.min` tall | `space.2xs` around the rows, rows 0 `space.md` | `typography.body` | Not given |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Raised surface, 1px default border, 12px corners, no shadow; groups split by a 1px subtle line | `color.surface.raised`, `border.width.default`, `color.border.default`, `radius.md`, `color.border.subtle`, `zIndex.dropdown` |
| hover | The row gets the secondary fill | `color.action.secondary.default` |
| active | The row gets the secondary hover fill | `color.action.secondary.hover` |
| focus | Focus ring on the row; arrow keys move between rows | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| disabled | Faded row text, cannot be chosen | `color.text.disabled` |
| loading | n/a: menu items are always ready | n/a |
| error | n/a: an action that fails shows an alert | n/a |
| empty | n/a: a menu always has at least one item | n/a |

#### Dropdown menu rules
- Destructive items (Delete) use `color.state.error` text with an icon and come last, after a subtle line. Why: color, icon, and text (2.3).
- Menus use `radius.md`. Why: not given.

### Toast
Purpose: a short confirmation that needs no action, such as "Saved". Never for errors.

Variants:
| Variant | When to use | Why |
|---|---|---|
| default | Confirmations: Saved, Copied | Not given |

Toast tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.toast.duration` | 5000ms | How long a toast stays | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | Fits one line, at least `component.tapTarget.min` | `space.sm` `space.md` | `typography.body` | Not given |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Bottom center, just above the chat input; raised surface, 1px default border, 12px corners, no shadow; text and a close button (ghost icon button, sm) | `color.surface.raised`, `border.width.default`, `color.border.default`, `radius.md`, `zIndex.toast` |
| hover | Stays while hovered | n/a |
| active | n/a: the toast itself is not pressable | n/a |
| focus | Stays while it or its close button has focus | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| disabled | n/a: a toast has nothing to switch off | n/a |
| loading | n/a: shown only once there is something to confirm | n/a |
| error | n/a: errors use an alert, which stays | n/a |
| empty | n/a: always has text | n/a |

#### Toast rules
- Toasts hide after `component.toast.duration`, never sooner. Screen readers announce them. Why: nothing important disappears; errors use alerts, which stay.

### Alert
Purpose: an inline message that stays where the problem is, such as "Couldn't load your sessions". Errors never use a toast.

Variants:
| Variant | When to use | Why |
|---|---|---|
| error | Something failed: stays until fixed, often with a Try again button (secondary) | Nothing important disappears |
| warning | Something may go wrong | Not given |
| info | Neutral information | Not given |
| success | Something worked and the learner should see it in place | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | Fits its text | `space.sm` `space.md` | `typography.body` | Not given |

States (all variants):
| State | What changes | Tokens |
|---|---|---|
| default | The variant's soft background, 12px corners, icon and text in the variant's color; info, warning, and success have a close button (ghost icon button, sm) | `color.state.errorBg`, `color.state.error`, `color.state.warningBg`, `color.state.warning`, `color.state.infoBg`, `color.state.info`, `color.state.successBg`, `color.state.success`, `radius.md` |
| hover | n/a: the alert itself is not interactive | n/a |
| active | n/a: the alert itself is not interactive | n/a |
| focus | n/a: its buttons take focus; screen readers announce it when it appears | n/a |
| disabled | n/a: the alert itself is not interactive | n/a |
| loading | Its Try again button shows its loading state | see Button |
| error | n/a: it is itself the error message | n/a |
| empty | n/a: always has text | n/a |

#### Alert rules
- Error alerts have no close button and stay until the problem is fixed. Why: honest about what went wrong.
- Every alert has an icon and text, never color alone (2.3). Why: color alone fails people with color blindness.

### Empty state
Purpose: what shows where content will be, before there is any, such as "No sessions yet".

Variants:
| Variant | When to use | Why |
|---|---|---|
| default | Any empty list or area | Guiding: always shows the next step |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | Fits its content, centered in the area | `space.card.padding` | title in `typography.cardTitle`, sentence in `typography.body` | Not given |

States:
| State | What changes | Tokens |
|---|---|---|
| default | A small plain icon, a one-line title, one helpful sentence in secondary text, one button (primary if it is the screen's main action) | `color.text.secondary`, `color.text.primary` |
| hover | n/a: its button has its own states | n/a |
| active | n/a: its button has its own states | n/a |
| focus | n/a: its button takes focus | n/a |
| disabled | n/a: its button has its own states | n/a |
| loading | n/a: loading shows a skeleton, not the empty state | n/a |
| error | n/a: a failure shows an alert, not the empty state | n/a |
| empty | n/a: it is itself the empty state | n/a |

#### Empty state rules
- No illustrations, only a small plain icon. Why: calm (section 1).

### Loading skeleton or spinner
Purpose: shows that something is loading. Skeletons for content and lists; spinners only inside buttons.

Variants:
| Variant | When to use | Why |
|---|---|---|
| skeleton | Lists and content: grey placeholder shapes the size of the coming content | Calmer and more honest than a spinning wheel |
| spinner | Only inside buttons and icon buttons while they load | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| skeleton | The size of the content it stands for | n/a: matches the content | n/a: no text | Shows the shape of what is coming |
| spinner | The icon size (section 9) | n/a: centered in its button | n/a: no text | Not given |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Skeleton: subtle fill, the same corners as the content it stands for; still or gently pulsing (section 8). Spinner: in the button's text color | `color.bg.subtle` |
| hover | n/a: not interactive | n/a |
| active | n/a: not interactive | n/a |
| focus | n/a: not interactive; screen readers hear "Loading" | n/a |
| disabled | n/a: not interactive | n/a |
| loading | n/a: it is itself the loading state | n/a |
| error | n/a: replaced by an alert if loading fails | n/a |
| empty | n/a: replaced by the empty state if there is nothing | n/a |

### Card
Purpose: a contained block of content, such as a saved artifact or a settings group.

Variants:
| Variant | When to use | Why |
|---|---|---|
| static | Content only | Not given |
| clickable | The whole card opens something, such as an artifact | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | Fits its content | `space.card.padding` | title in `typography.cardTitle` | Same look as the quiz card |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Surface fill, 1px default border, 12px corners, no shadow | `color.surface.default`, `border.width.default`, `color.border.default`, `radius.md` |
| hover | Clickable only: the border becomes strong | `color.border.strong` |
| active | Clickable only: the secondary fill | `color.action.secondary.default` |
| focus | Clickable only: focus ring | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| disabled | n/a: a card that cannot be opened is static | n/a |
| loading | A skeleton of the card | see Loading skeleton or spinner |
| error | An alert inside the card | see Alert |
| empty | The empty state inside the card | see Empty state |

### Avatar
Purpose: the learner's account button in the top bar: a circle with their initials, opening the account menu (Sign out). Used nowhere else.

Variants:
| Variant | When to use | Why |
|---|---|---|
| initials | The account button | Not given |

Avatar tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.avatar.size` | 32px | Visible circle, inside a 44px tap area | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | `component.avatar.size`, round | n/a: initials centered | `typography.label` | Not given |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Secondary fill, initials in primary text, fully round | `color.action.secondary.default`, `color.text.primary`, `radius.full` |
| hover | Secondary hover fill | `color.action.secondary.hover` |
| active | Secondary active fill | `color.action.secondary.active` |
| focus | Focus ring | `component.focusRing.width`, `component.focusRing.offset`, `color.focus.ring` |
| disabled | n/a: the account menu is always available | n/a |
| loading | n/a: initials are known after sign-in | n/a |
| error | n/a: nothing to fail | n/a |
| empty | n/a: a signed-in learner always has a name; the screen reader name is "Account" | n/a |

### Top bar
Purpose: the bar across the top of the app.

Variants:
| Variant | When to use | Why |
|---|---|---|
| laptop | 640px and up: left panel button and Polaris logo on the left, session title in the middle, tools panel button and account on the right | Not given |
| phone | Below 640px: menu button and logo on the left, session title in the middle, account on the right; tools open from the chat input | Set in section 6 |

Top bar tokens:
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.topBar.height` | 56px | Top bar height | Not given |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| md | `component.topBar.height` | 0 `layout.page.margin` (`layout.page.marginPhone` on phones) | session title in `typography.label`, one line, cut with "..." | Not given |

States:
| State | What changes | Tokens |
|---|---|---|
| default | Page background, a 1px subtle line at the bottom, stays on top while scrolling | `color.bg.page`, `border.width.default`, `color.border.subtle`, `zIndex.sticky` |
| hover | n/a: its buttons have their own states | n/a |
| active | n/a: its buttons have their own states | n/a |
| focus | n/a: its buttons take focus | n/a |
| disabled | n/a: the bar is always there | n/a |
| loading | n/a: the title shows once known | n/a |
| error | n/a: errors show in alerts | n/a |
| empty | No session open: the title area is blank | n/a |

## 8. Motion

### 8.1 Motion tokens
| Token | Value | Used for | Why |
|---|---|---|---|
| `motion.duration.fast` | 100ms | Hover and press color changes, things closing | Quick; nothing in the UI waits on it |
| `motion.duration.normal` | 200ms | Menus, toasts, dialogs fading in | Not given |
| `motion.duration.slow` | 300ms | Drawer, bottom sheet, progress bar | The longest UI motion, so nothing feels slow |
| `motion.duration.pulse` | 1600ms | One cycle of a loading pulse (thinking star, skeletons) | Slow enough to feel calm, not urgent |
| `motion.duration.spin` | 800ms | One turn of the button spinner | Not given |
| `motion.easing.standard` | cubic-bezier(0.2, 0, 0, 1) | Things appearing or moving in | Starts quickly and settles gently: calm and natural |
| `motion.easing.exit` | cubic-bezier(0.3, 0, 1, 1) | Things leaving | Speeds up as it goes, so leaving never lingers |
| `motion.easing.pulse` | cubic-bezier(0.4, 0, 0.6, 1) | Loading pulses | Even in and out, so the loop has no jolt |
| `motion.easing.linear` | linear | The spinner only | Constant speed for something that turns |

### 8.2 What animates
| Element or change | Property | Duration | Easing | Why |
|---|---|---|---|---|
| Hover and press on buttons, rows, borders | background color, border color, text color | `motion.duration.fast` | `motion.easing.standard` | Feedback that something responds |
| Dropdown menu opening | opacity | `motion.duration.normal` | `motion.easing.standard` | Not given |
| Dropdown menu, modal, toast closing | opacity | `motion.duration.fast` | `motion.easing.exit` | Leaving never lingers |
| Modal opening, with its dim layer | opacity | `motion.duration.normal` | `motion.easing.standard` | Not given |
| Drawer opening | slides in from the left | `motion.duration.slow` | `motion.easing.standard` | Shows where it came from |
| Drawer closing | slides out to the left | `motion.duration.normal` | `motion.easing.exit` | Shows where it went |
| Bottom sheet opening, and settling after a drag | slides up | `motion.duration.slow` | `motion.easing.standard` | Shows where it came from |
| Bottom sheet closing | slides down | `motion.duration.normal` | `motion.easing.exit` | Shows where it went |
| Toast appearing | opacity, and moves up 8px | `motion.duration.normal` | `motion.easing.standard` | Not given |
| Result feedback appearing | opacity | `motion.duration.normal` | `motion.easing.standard` | Not given |
| Progress bar fill | width | `motion.duration.slow` | `motion.easing.standard` | Progress feels earned, not jumpy |
| Thinking star and skeletons | opacity between 100% and 40%, looping | `motion.duration.pulse` | `motion.easing.pulse` | Shows work in progress, never a frozen screen (section 1) |
| Button spinner | turns, looping | `motion.duration.spin` | `motion.easing.linear` | Not given |

### 8.3 Motion rules
- Never animated: text, focus rings, tabs, chat messages appearing, the tutor's reply text as it arrives, and side panels opening or closing on laptops (the layout changes instantly). Why: motion only when it has a job; moving text and layout is tiring.
- No scroll-triggered effects and no decorative motion. Why: calm (section 1).
- No UI motion longer than `motion.duration.slow`, except the looping pulse and spinner. Why: nothing should feel slow.
- When the device asks for reduced motion: nothing moves or slides; things appear with a fade of `motion.duration.fast` only; the pulse and spinner stop (the star and spinner stay still, and the status text still says what is happening). Why: some people feel unwell from motion; the meaning is never lost.
- The tutor's teaching animations are content, not UI, and are not covered by these rules, except that they never play on their own under reduced motion. Why: not given.

## 9. Icons and imagery

### 9.1 Icons
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.icon.size.sm` | 16px | Icons next to small text: alerts, feedback, error messages under fields | Matches 14px text |
| `component.icon.size.md` | 20px | Icons in buttons, inputs, menus, icon buttons | Not given |
| `component.icon.size.lg` | 24px | Top bar and whiteboard toolbar | Not given |
| `component.icon.strokeWidth` | 2px | Line thickness of every icon | Easier to see than 1.5px; Lucide's default |

Icon set: Lucide (lucide.dev), outline icons with rounded line ends.

### 9.2 Imagery
Photos: none anywhere in the app.
Illustrations: none in the app's own UI. The tutor's drawings and animations are content, not UI.
Logo and Polaris star mark: TBD (no logo yet).

### 9.3 Icon and imagery rules
- Only Lucide icons, never mixed with another set. Why: one consistent line style.
- An icon takes the color of the text next to it, or its button's text color. State colors only in alerts, result feedback, and error messages. Why: nothing extra to keep consistent.
- Icon sizes by place: `component.icon.size.sm` next to small text, `component.icon.size.md` in buttons, inputs, and menus, `component.icon.size.lg` in the top bar and whiteboard toolbar. Why: not given.
- An icon with no visible text has a screen reader name (see Icon button). An icon next to text is hidden from screen readers. Why: screen reader users hear each thing once.
- No photos and no illustrations in the UI. Why: calm (section 1), matching the empty state rule.

## 10. Voice and copy

### 10.1 Tone
| Word | What it means in practice |
|---|---|
| Plain | Short sentences, everyday words, no jargon: "Couldn't save", not "Persistence failure". |
| Warm | Kind and encouraging, never cheerleading: "Nice work" is fine, "Amazing!!!" is not. |
| Honest | Says what really happened and what Polaris cannot do. Never a vague "Something went wrong" on its own. |

### 10.2 Copy patterns
| Kind | Pattern | Good example | Bad example | Why |
|---|---|---|---|---|
| Button | Verb plus object, sentence case | Start quiz | OK, Submit | Says what will happen |
| Error message | What happened, then what to do next. Never blames the learner | Couldn't load your sessions. Check your connection and try again. | Oops! Something went wrong. | Honest, and gives a next step |
| Empty state | What will be here, then one action | No sessions yet. Ask Polaris anything to start one. [Start a session] | Nothing to see here! | Guiding: always a next step |
| Confirmation | A question naming the thing, the consequence, verb buttons | Delete this session? This can't be undone. [Delete session] [Cancel] | Are you sure? [Yes] [No] | The learner knows exactly what they are agreeing to |
| Quiz feedback | Right: "Correct" plus why. Wrong: "Not quite, here's why" plus the explanation | Not quite, here's why: ... | Wrong! | Reassuring: mistakes are part of learning |

### 10.3 Words to avoid
| Avoid | Use instead | Why |
|---|---|---|
| Oops, Uh oh, Whoops | Say what happened | Filler that does not help |
| Something went wrong (alone) | Name what failed and what to do | Honest |
| Get started | The real action: Start a session | Says what will happen |
| Unlock, Supercharge, Seamless, Revolutionize, Elevate, Effortless, Magic, AI-powered | A plain description of what it does | Hype makes every product sound the same |
| Simply, just, easy, obviously | Leave the word out | Makes a struggling learner feel bad |
| Wrong, Incorrect, Failed (about the learner) | Not quite | Reassuring (section 1) |
| Are you sure? | Name the action and its consequence | Honest |
| Submit, OK, Yes, No (as buttons) | The real action | Says what will happen |
| We | You, or Polaris | No company "we" behind a personal app |

### 10.4 Voice rules
- Sentence case everywhere: buttons, headings, labels, menu items, tabs. Why: calmer and easier to read.
- No exclamation marks in UI text. Why: calm, and forced cheerfulness reads as fake.
- The app speaks to "you" and never says "we". The tutor is "Polaris". Why: one person, one local app, no company behind the voice.
- When Polaris cannot do something, it says so plainly and offers what it can do. Why: Trustworthy, honest about limits (section 1).
- Errors never blame the learner. Why: Reassuring (section 1).

## 11. Banned defaults

The full list lives in banned.md. Summary: 25 bans in four groups: AI visual cliches (gradients, glass, glows, blobs, shadows, emoji icons), landing page shapes, hype and filler copy, and AI tutor cliches (dots, sparkles, typing dots, robot icons).

## 12. Gap rule

Gap rule: mixed
Flag format: `DS-GAP: <what was missing>, used <token>`

### 12.1 Gap rules
- Small things (a spacing, a color shade, a radius, a size, a duration): use the closest existing token, and put the flag comment in the code next to it, for example `DS-GAP: gap between quiz summary rows, used space.md`. Why: building never stops for small choices, and every guess can be reviewed later.
- "Closest" means the same token group and the nearest value. On a tie, use the smaller one. Why: one predictable answer, and smaller keeps things calm.
- New things (a new component, a new color, a new pattern, a new variant): stop and ask before building. Why: new things shape the product, so they are never guessed.
- Anything this document still lists as undecided (such as the tooltip's look or the end-of-quiz summary) counts as new: stop and ask. Why: undecided means not decided yet, not "pick anything".
- A banned item with an empty "Instead" in banned.md counts as new: stop and ask. Why: the ban says what not to do, not what to do.

## 13. Do and don't examples

### <Component name>
| Do | Don't | Why |
|---|---|---|
| TBD | TBD | TBD |

Reference screenshot: TBD (path relative to this folder, or "none")

## Open questions
- Section 1: more reference products. The user has more in mind.
- Section 7: Link active state (same as hover, or thicker underline plus `color.text.secondary`).
- Section 7: Tooltip look, including its fill color, and a use case. When decided, add a contrast pair for `color.text.inverse` or drop that token.
- Section 7: the end-of-quiz summary ("See results") look.
- Section 9: the logo and Polaris star mark (used in tutor messages, the thinking indicator, and the top bar).
- Section 13: do and don't pairs and reference screenshots. Skipped for now; a draft of six pairs was offered in the interview.
