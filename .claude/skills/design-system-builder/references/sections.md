# Question bank, by section

Use the section you are on. Each section lists what it must end up recording, then the questions grouped into turns. Ask one turn at a time (2 to 4 questions), wait for the answer, then move to the next turn. Skip any question the user has already answered. Explain any design word the first time you use it, in one short plain sentence.

Options are shown as a numbered plain-text list so the user can type a number or their own answer. Options are examples to react to, never a default: nothing is written until the user picks or types a value.

## Contents
1. Product context
2. Colors
3. Typography
4. Spacing
5. Radius, borders, shadows
6. Layout
7. Components
8. Motion
9. Icons and imagery
10. Voice and copy
11. Banned defaults
12. Gap rule
13. Do and don't examples

---

## 1. Product context

Must record: what it is, who uses it, 3 to 5 feel words each turned into something concrete, 2 to 4 reference products each with what to take and what not to take.

Turn 1
- In one or two sentences, what is the product?
- Who uses it, and in what situation? (For example: "clinic staff, on a desktop, between patients, in a hurry")
- Is this design system for the whole product or one part of it (for example the marketing site, the app, the admin area)?

Turn 2
- Give me 3 to 5 words for how it should feel.
- Feel words are vague by nature, so for each one ask what it means on screen. Example: "calm" might mean "few colors, lots of space, no animation except feedback". Record the concrete meaning, not the word alone.

Turn 3
- Name 2 to 4 products or sites whose design you like.
- For each: what exactly do you like (the font, the use of space, the colors, how forms look)? And is there anything about it you do not want?

Watch for: "I like Stripe" with no detail. Ask what specifically, once.

---

## 2. Colors

Must record: every color tied to a role, light and (if wanted) dark values, contrast results for every text and UI pair, rules for when colors are used.

Explain once: "A color role is the job a color does, like 'main button' or 'error text'. We name colors by job, so changing the blue later does not mean renaming anything."

Turn 1
- Do you want dark mode? 1. yes, from the start 2. no 3. later (we record "no" now and you can add it with an update)
- Do you already have brand colors? Give hex codes if you have them (a hex code looks like #1a73e8). If you have a logo file or a site, I can read colors from it if you give me the path.
- Show the suggested role list from `tokens-schema.md` and ask which roles to drop or add.

Turn 2 and on, one role group per turn (backgrounds and surfaces, text, borders, actions, states, focus)
- Ask for the hex value for each role in the group, light then dark.
- If the user does not know, offer to show 2 or 3 options that fit what they said in section 1, as hex codes with a plain description ("#1f2937, a very dark blue-gray"). They pick or adjust. You never pick.
- For action colors, ask for hover, active, and disabled separately. Hover is not automatically "10% darker" unless the user says so and gives the exact value.

Contrast
- After the text, border, and action colors are in, run `check_sync.py` (it computes contrast for the 2.2 table). Fill the ratios in from its output.
- Pairs to include at least: each text color on `color.bg.page` and on each surface, `color.text.onAction` on each action color, each state color on its background, `color.border.default` and `color.focus.ring` on the page (kind `ui`).
- If a pair fails AA, tell the user plainly which pair, the ratio, and what is needed ("4.5:1 for normal text, this is 3.2:1"). Ask whether to change one of the colors or keep it with a recorded reason. Do not change it yourself.

Rules to ask about
- Where is the primary action color allowed (buttons only, also links, also icons)?
- Is there more than one primary button per screen allowed?
- How are errors shown besides color (icon, text)? Color alone fails people with color blindness.

---

## 3. Typography

Must record: font families with fallback stacks and where they load from, a fixed size scale, weights, line heights, letter spacing, and the text style table for page title, section title, card title, body, small, label, button.

Explain once: "A type scale is a short fixed list of font sizes. Every text on screen uses one of them, which is what makes a UI look consistent."

Turn 1
- Which font or fonts? 1. one font for everything 2. one for headings, one for body 3. add a monospace font for code or numbers
- If they do not know: ask what the reference products from section 1 use and whether they want something like it. Offer 2 or 3 named fonts with a one-line description each. Note that picking Inter or the system font only because it is the default is on the banned starter list, but choosing it on purpose is fine.
- Where do the fonts come from (Google Fonts, files you have, a paid license)?
- What fallback fonts if it fails to load?

Turn 2
- Sizes: how many sizes in the scale (usually 5 to 8), and the exact values? px or rem? Offer a sample scale as an option only, for example "12, 14, 16, 20, 24, 32".
- Body text size?
- Weights you will use (for example 400 regular, 500 medium, 600 semibold)? Fewer weights means less to load.

Turn 3
- Line height for body text and for headings (for example 1.5 and 1.2)?
- Letter spacing: none, or tighter on large headings, or wider on small caps labels? Exact values.

Turn 4
- Walk through the text style table one row at a time: page title, section title, card title, body, small, label, button. Each row picks from the scale. Ask whether any text is uppercase.

Rules to ask about
- Max line length for reading text (for example 70 characters)?
- Are bold and italic allowed inside body text?
- How are numbers shown in tables (tabular figures)?

---

## 4. Spacing

Must record: a fixed spacing scale, and gap roles for inside cards, between sections, between form fields, label to input, default stack and inline gaps.

Explain once: "Spacing is the empty space between and inside things. A fixed scale means every gap is one of a few sizes, never a one-off like 13px."

Turn 1
- What base unit? 1. 4px 2. 8px 3. other
- Exact scale values (for example 4, 8, 12, 16, 24, 32, 48, 64)? Each becomes `space.xs`, `space.sm`, and so on.
- How dense should screens feel: tight (lots of information visible), balanced, or roomy? Then turn that into the gap values below.

Turn 2
- Padding inside cards? Between page sections? Between form fields? Between a label and its input?
- Default gap between stacked items and between items in a row?

Rules to ask about
- Can a value outside the scale ever be used? (Usual answer: no.)
- Does spacing shrink on mobile? By how much, exactly?

---

## 5. Radius, borders, shadows

Must record: radius values and where each is used, border widths and where borders are used, whether shadows are allowed at all, and if yes exact shadow values and where each is used.

Turn 1, radius
- Explain: "Radius is how rounded corners are. 0 is sharp, 4px is slightly soft, 9999px is a pill."
- Which radius values, and which is used for buttons, inputs, cards, modals, tags, avatars?

Turn 2, borders
- Border width (usually 1px)? A second width for focus or selected?
- Where do borders appear: around cards, inputs, tables, dividers between list items? Which border color token for each?

Turn 3, shadows
- Ask directly: "Are shadows allowed at all? 1. no shadows anywhere 2. only on things that float above the page (menus, modals, toasts) 3. also on cards"
- If yes: exact values for each level (offset, blur, spread, color with transparency), and the list of what uses each.
- If no: how do floating things (menus, modals) separate from the page instead? (border, background color, overlay)

---

## 6. Layout

Must record: grid columns and gutter, page margins, max content widths, breakpoints, z-index layers, how layouts change on mobile.

Explain once: "A breakpoint is a screen width where the layout changes, for example from two columns to one."

Turn 1
- Main devices: 1. mostly desktop 2. mostly phone 3. both equally
- Grid: how many columns, and the gap between them? Page side margins on desktop and on phone?
- Max width of the main content area? Max width for reading text and for forms, if different?

Turn 2
- Breakpoints: exact widths (for example 640, 768, 1024, 1280)? Name them `breakpoint.sm`, `.md`, and so on.
- For each common layout the product has (ask which: sidebar plus content, list and detail, dashboard of cards, form page), what happens on a phone? Example: "sidebar becomes a top menu button", "table becomes stacked cards".

Turn 3
- Z-index layers: explain "which things sit on top of which". Usual layers: dropdown, sticky header, overlay, modal, toast, tooltip. Ask for the order and exact numbers.

Rules to ask about
- Minimum tap target size on touch screens (for example 44px)?
- Is horizontal scrolling ever allowed (for example in wide tables)?

---

## 7. Components

Must record: the component list, and for each one its purpose, variants, sizes, every state (default, hover, active, focus, disabled, loading, error, empty) with what changes and which tokens it uses, plus component rules.

Turn 1
- "Which components do you need? Here is a common list, pick and add: button, link, text input, textarea, select, checkbox, radio, toggle, card, modal, dropdown menu, tabs, table, list, toast or alert, badge or tag, tooltip, avatar, navigation bar, sidebar, empty state, loading skeleton or spinner, pagination."
- "Which 3 to 5 are most important?" Do those first, since the rest often copy from them.

Then, for each component, one or two turns
- What is it for, and when should it NOT be used?
- Variants (for a button: primary, secondary, ghost, destructive)? When is each used?
- Sizes, with exact height, padding, and text style for each?
- States: go through all eight. For each, what changes (color, border, icon, text) and which token. If a state does not apply, ask why and record `n/a: <reason>` (for example a card has no "loading" if the page shows a skeleton instead).
- Focus: what does the focus ring look like (width, offset, color token)? This is required for keyboard users.
- Loading: does the button keep its width, show a spinner, disable clicks?

Watch for: a state described in words like "slightly darker". Ask for the token or hex.

---

## 8. Motion

Must record: durations, easing curves, what animates and how, what never animates, reduced-motion behavior.

Explain once: "Easing is the speed curve of an animation: whether it starts fast and slows down, or the reverse."

Turn 1
- How much motion overall? 1. none except feedback (hover, focus, loading) 2. small transitions on things that open and close 3. more expressive
- Exact durations (for example fast 100ms, normal 200ms, slow 300ms)?
- Easing curves, as cubic-bezier values? Offer named examples with their values if the user does not know.

Turn 2
- For each thing that animates (hover color, menu open, modal open, toast in and out, page change): property, duration token, easing token.
- What must never animate? (Common: layout shifts, text, anything over 400ms, scroll-triggered fades.)
- Reduced motion: when the user's device asks for less motion, what happens? 1. all motion off 2. only fades kept, no movement 3. other

---

## 9. Icons and imagery

Must record: icon set, sizes, stroke width, color rules, photo style, illustrations yes or no.

Turn 1
- Which icon set? Give 2 or 3 options with a one-line description (for example Lucide: thin outline icons; Phosphor: several weights; Material Symbols). Or a custom set?
- Icon sizes (for example 16px inline, 20px in buttons, 24px in nav) and stroke width (for example 1.5px)?
- Icon color: same as nearby text, or its own token?

Turn 2
- Are photos used? If yes: what kind (real people, products, places), what style (bright, muted, black and white), any treatment (rounded, cropped to a ratio)?
- Illustrations: yes or no? If yes, what style, and where?
- Are icons ever used without a text label? If yes, they need a tooltip and an accessible name.

---

## 10. Voice and copy

Must record: tone, button wording pattern, error message pattern, empty state pattern, confirmation pattern, words to avoid.

Turn 1
- How should the product talk? Ask for 2 or 3 words, then make each concrete, same as the feel words. Example: "direct" means "short sentences, no 'please', no exclamation marks".
- Who is "you" and who is "we"? Does the product say "we" at all?
- Sentence case or Title Case for buttons and headings?

Turn 2
- Buttons: verb first and specific ("Save changes", "Send invoice")? Give one good and one bad example to confirm.
- Error messages: what happened, and what to do next? Is blame ever on the user? Example good and bad.
- Empty states: what is shown when a list is empty? Explain plus one action? Example.

Turn 3
- Words to avoid, and what to use instead. Offer the copy items from the banned starter list as prompts.

---

## 11. Banned defaults

Must record: banned.md with every banned item, what to use instead, and why.

Turn 1
- Show the full numbered list from `banned-defaults-starter.md` with reasons. Ask which numbers to ban.

Turn 2
- "Anything else you have seen AI-built UIs do that you never want here?" Add each with a why.
- For each banned item where "instead" is not already clear from earlier sections, ask what to do instead.

---

## 12. Gap rule

Must record: what an AI building UI should do when DESIGN.md does not cover something, and the exact flag format.

Turn 1
- Explain: "Later, an AI will build screens using this document. Sometimes it will need something we did not decide. This rule tells it what to do."
- Options:
  1. Use the closest existing token and flag it in the code, so you can review it later.
  2. Stop and ask you before building it.
  3. Mix: closest token for small things (a spacing or color choice), stop and ask for anything new (a new component, a new color).
- If 1 or 3: what should the flag look like? Suggest `DS-GAP: <what was missing>, used <token>` as a code comment, and ask if they want something else.
- Record in DESIGN.md as `Gap rule: closest-token-and-flag`, `stop-and-ask`, or `mixed`, with `Flag format:` on the next line, and the details as bullets under 12.1.

---

## 13. Do and don't examples

Must record: for each of the most important components (from section 7), at least one do and don't pair or a reference screenshot path.

Turn 1, per component
- "Describe one right way and one wrong way to use <component>." Example for a button: Do "one primary button per form, at the bottom right", Don't "two primary buttons side by side".
- "Do you have a screenshot of a good example? Give the file path, and I will copy it into this design system folder under `examples/`." Record the path relative to the folder.
