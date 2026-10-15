# DESIGN.md template

This is the exact structure of `design-system/<name>/DESIGN.md`. The enforcement skill and `scripts/check_sync.py` both rely on it, so:

- Keep every `##` heading below, with the same number and wording, in the same order. Never rename, reorder, or drop one. A section that is not decided yet keeps its heading and says `TBD`.
- Keep the table column names exactly as shown. The script finds columns by name (`Token`, `Value`, `Light`, `Dark`, `Why`).
- Write token names in backticks, like `color.text.primary`. A backticked dotted name whose first part is a token group (`color`, `font`, `typography`, `space`, `radius`, `border`, `shadow`, `motion`, `layout`, `breakpoint`, `zIndex`, `opacity`, `component`) is read as a token reference and must exist in `tokens.json`.
- Every row in a table with a `Why` column needs a why. Every bullet under a heading that contains the word "Rules" needs `Why:` in it. If the user gave no reason, write `Why: not given`.
- No em dashes anywhere. Use commas, colons, or full stops.

When starting a new design system, copy the skeleton below into the file with every value set to `TBD`, then fill sections as the interview confirms them.

---

## Skeleton

```markdown
# Design system: <name>

Status: In progress
Last updated: <YYYY-MM-DD>
Tokens file: tokens.json
Banned defaults: banned.md

## 1. Product context

### What it is
TBD

### Who uses it
TBD

### How it should feel
| Word | What it means in practice | Why |
|---|---|---|
| TBD | TBD | TBD |

### Reference products
| Product or site | What exactly to take from it | What not to take from it |
|---|---|---|
| TBD | TBD | TBD |

## 2. Colors

### 2.1 Color tokens
Dark mode: TBD (yes or no)

| Token | Light | Dark | Used for | Why |
|---|---|---|---|---|
| `color.bg.page` | TBD | TBD | Page background | TBD |
| `color.text.primary` | TBD | TBD | Main text | TBD |

If dark mode is "no", delete the `Dark` column.

### 2.2 Contrast checks
| Text | Background | Kind | Light ratio | Dark ratio | Result |
|---|---|---|---|---|---|
| `color.text.primary` | `color.bg.page` | text | TBD | TBD | TBD |

Kind is `text` (needs 4.5:1), `large` (text 24px+ or 18.66px+ bold, needs 3:1), or `ui` (borders, icons, focus ring, needs 3:1). Ratios come from `check_sync.py`, never from estimation.

### 2.3 Color rules
- TBD

## 3. Typography

### 3.1 Font families
| Token | Value | Used for | Why |
|---|---|---|---|
| `font.family.body` | TBD | TBD | TBD |

Font source: TBD (for example Google Fonts, self-hosted files, licensed)

### 3.2 Scales
| Token | Value | Used for | Why |
|---|---|---|---|
| `font.size.md` | TBD | TBD | TBD |
| `font.weight.regular` | TBD | TBD | TBD |
| `font.lineHeight.normal` | TBD | TBD | TBD |
| `font.letterSpacing.normal` | TBD | TBD | TBD |

### 3.3 Text styles
| Token | Family | Size | Weight | Line height | Letter spacing | Used for | Why |
|---|---|---|---|---|---|---|---|
| `typography.pageTitle` | TBD | TBD | TBD | TBD | TBD | Page title | TBD |
| `typography.sectionTitle` | TBD | TBD | TBD | TBD | TBD | Section title | TBD |
| `typography.cardTitle` | TBD | TBD | TBD | TBD | TBD | Card title | TBD |
| `typography.body` | TBD | TBD | TBD | TBD | TBD | Body text | TBD |
| `typography.small` | TBD | TBD | TBD | TBD | TBD | Small text | TBD |
| `typography.label` | TBD | TBD | TBD | TBD | TBD | Form labels | TBD |
| `typography.button` | TBD | TBD | TBD | TBD | TBD | Button text | TBD |

Cells in Family to Letter spacing hold token references from 3.1 and 3.2.

### 3.4 Typography rules
- TBD

## 4. Spacing

### 4.1 Spacing scale
| Token | Value | Why |
|---|---|---|
| `space.md` | TBD | TBD |

### 4.2 Common gaps
| Token | Value | Used for | Why |
|---|---|---|---|
| `space.card.padding` | TBD | Inside cards | TBD |
| `space.section.gap` | TBD | Between page sections | TBD |
| `space.form.fieldGap` | TBD | Between form fields | TBD |
| `space.form.labelGap` | TBD | Label to input | TBD |
| `space.stack.default` | TBD | Default gap between stacked items | TBD |
| `space.inline.default` | TBD | Default gap between items in a row | TBD |

Values here are references to the scale in 4.1, like `{space.md}` in tokens.json and the resolved px value in this table.

### 4.3 Spacing rules
- TBD

## 5. Radius, borders, shadows

### 5.1 Radius
| Token | Value | Used for | Why |
|---|---|---|---|
| `radius.md` | TBD | TBD | TBD |

### 5.2 Borders
| Token | Value | Used for | Why |
|---|---|---|---|
| `border.width.default` | TBD | TBD | TBD |

### 5.3 Shadows
Shadows allowed: TBD (yes or no)

| Token | Value | Used for | Why |
|---|---|---|---|
| `shadow.md` | TBD | TBD | TBD |

If shadows are not allowed, delete the table and write one rule in 5.4 saying so.

### 5.4 Radius, border, and shadow rules
- TBD

## 6. Layout

### 6.1 Grid
| Token | Value | Used for | Why |
|---|---|---|---|
| `layout.grid.columns` | TBD | TBD | TBD |
| `layout.grid.gutter` | TBD | TBD | TBD |
| `layout.page.margin` | TBD | TBD | TBD |

### 6.2 Max content widths
| Token | Value | Used for | Why |
|---|---|---|---|
| `layout.maxWidth.content` | TBD | TBD | TBD |

### 6.3 Breakpoints
| Token | Value | Used for | Why |
|---|---|---|---|
| `breakpoint.md` | TBD | TBD | TBD |

### 6.4 Z-index
| Token | Value | Used for | Why |
|---|---|---|---|
| `zIndex.dropdown` | TBD | TBD | TBD |

### 6.5 Layout rules
Include how each kind of layout changes on mobile.
- TBD

## 7. Components

Component list: TBD

### <Component name>
Purpose: TBD

Variants:
| Variant | When to use | Why |
|---|---|---|
| TBD | TBD | TBD |

Sizes:
| Size | Height | Padding | Text style | Why |
|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD |

States (variant: <variant name>):
| State | What changes | Tokens |
|---|---|---|
| default | TBD | TBD |
| hover | TBD | TBD |
| active | TBD | TBD |
| focus | TBD | TBD |
| disabled | TBD | TBD |
| loading | TBD | TBD |
| error | TBD | TBD |
| empty | TBD | TBD |

A state that cannot happen for this component says `n/a: <reason>`. Repeat the States table for each variant that looks different.

#### <Component name> rules
- TBD

## 8. Motion

### 8.1 Motion tokens
| Token | Value | Used for | Why |
|---|---|---|---|
| `motion.duration.fast` | TBD | TBD | TBD |
| `motion.easing.standard` | TBD | TBD | TBD |

### 8.2 What animates
| Element or change | Property | Duration | Easing | Why |
|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD |

### 8.3 Motion rules
Include what never animates and what happens under reduced motion.
- TBD

## 9. Icons and imagery

### 9.1 Icons
| Token | Value | Used for | Why |
|---|---|---|---|
| `component.icon.size.md` | TBD | TBD | TBD |
| `component.icon.strokeWidth` | TBD | TBD | TBD |

Icon set: TBD

### 9.2 Imagery
Photos: TBD
Illustrations: TBD

### 9.3 Icon and imagery rules
- TBD

## 10. Voice and copy

### 10.1 Tone
TBD

### 10.2 Copy patterns
| Kind | Pattern | Good example | Bad example | Why |
|---|---|---|---|---|
| Button | TBD | TBD | TBD | TBD |
| Error message | TBD | TBD | TBD | TBD |
| Empty state | TBD | TBD | TBD | TBD |
| Confirmation | TBD | TBD | TBD | TBD |

### 10.3 Words to avoid
| Avoid | Use instead | Why |
|---|---|---|
| TBD | TBD | TBD |

### 10.4 Voice rules
- TBD

## 11. Banned defaults

The full list lives in banned.md. Summary: TBD

## 12. Gap rule

Gap rule: TBD
Flag format: TBD

### 12.1 Gap rules
- TBD

## 13. Do and don't examples

### <Component name>
| Do | Don't | Why |
|---|---|---|
| TBD | TBD | TBD |

Reference screenshot: TBD (path relative to this folder, or "none")

## Open questions
- TBD items collected during the interview, one per line, with the section number.
```

---

## Formats for the other files

### banned.md

```markdown
# Banned defaults: <name>

These are banned in this design system. If code would use one of these, use the "Instead" column. If "Instead" is empty, follow the gap rule in DESIGN.md section 12.

| Banned | Instead | Why |
|---|---|---|
| Purple or blue gradients | Flat `color.action.primary` | Reads as generic AI output |
```

### CHANGELOG.md

```markdown
# Changelog: <name>

Newest first. Deciding a value for the first time is not a change and is not logged. Changing a value that was already confirmed is.

| Date | What changed | Old value | New value | Why |
|---|---|---|---|---|
| 2026-01-31 | Created design system | none | none | Started interview |
```
