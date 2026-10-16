---
name: polaris-ui
description: Build or redesign Polaris UI so it follows the polaris-design system (design-system/polaris-design). Use this skill every time the task adds a new UI element (button, input, card, modal, panel, toast, page, layout, empty state, icon, copy) or changes how something looks (restyle, redesign, spacing, color, typography, dark mode, motion, UI text), in web/src or anywhere else the learner sees. Use it even when the user does not say "design system" or "style", and even for a small tweak to CSS or a component's markup.
---

# Polaris UI

Polaris has a written design system. Without it, UI drifts toward the generic AI-product look the system bans. So read the rules before drawing anything, and take every value from the tokens instead of choosing one.

Files, all in `design-system/polaris-design/`:

- `DESIGN.md` is the source of truth (about 1500 lines). Do not read it whole.
- `tokens.json` holds every token value, with dark-mode values under `$extensions.modes.dark`.
- `banned.md` lists defaults to avoid, each with what to use instead.
- `CHANGELOG.md` records changes to confirmed values.

## Workflow

1. **Read `banned.md`** (short). Check the planned UI against it before and after building.
2. **Find the sections you need in `DESIGN.md`** with `grep -n '^#' design-system/polaris-design/DESIGN.md`, then read only those line ranges:
   - Always read section 7 for the component you are touching or building. Each component has its states, sizes, and its own rules. If it is a new element that resembles an existing one (a drawer next to a side panel), read both.
   - Read the matching foundation section when the task touches it: 2 color, 3 typography, 4 spacing, 5 radius/borders/shadows, 6 layout, 8 motion, 9 icons, 10 voice and copy.
   - Read section 1 (product context) once if you are making a layout or page decision.
3. **Use tokens, not literals.** The web app mirrors the tokens as CSS custom properties in `web/src/index.css`, named like `--color-text-primary`. Use those variables. Never write a hex color, a pixel size, a radius, or a font name that a token already covers. Dark mode comes from the same variables, so a token-only style works in both modes. Check both.
4. **Reuse before building.** Look in `web/src/chat/ui.tsx` and the existing components for one that already does the job, and extend it instead of adding a near-duplicate. Icons come from `lucide-react`, with sizes and stroke widths from section 9.
5. **Write copy to section 10.** UI text follows the copy patterns, avoids the listed words, and uses no exclamation marks.
6. **Check the result** against the "rules" subsection of each component you used, the banned list, and keyboard focus, labels, and contrast.

## When the system has no answer

If DESIGN.md does not cover the case, follow its section 12 (gap rule). Do not invent a value silently. Say what was missing in your reply so the user can decide.

If the user wants to change a value that is already confirmed, that is a design-system change, not a UI change. Tell them, update `tokens.json` and `DESIGN.md` together, and add a row to `CHANGELOG.md`. The `design-system-builder` skill handles that flow. Then sync `web/src/index.css` to match.

## Why this matters

The user rejected specific generic patterns, such as status dots, sparkle icons, and gradients. They are in `banned.md` because they were decided, not guessed. Reading the component's rules each time is what keeps new UI looking like the same product.
