# tokens.json schema and naming

`design-system/<name>/tokens.json` holds every token in DESIGN.md, and nothing that is not in DESIGN.md. `scripts/check_sync.py` compares the two.

## Shape

The file follows the W3C Design Tokens format: nested groups, and a token is any object with a `$value` key.

```json
{
  "color": {
    "text": {
      "primary": {
        "$type": "color",
        "$value": "#1a1a1a",
        "$extensions": { "modes": { "dark": "#f2f2f2" } }
      }
    }
  },
  "space": {
    "md": { "$type": "dimension", "$value": "16px" },
    "card": {
      "padding": { "$type": "dimension", "$value": "{space.md}" }
    }
  }
}
```

- Token name = the path joined with dots: `color.text.primary`, `space.card.padding`.
- `$value` is the light mode value (or the only value).
- Dark mode values go in `$extensions.modes.dark`. Only color tokens normally have one.
- A value may point at another token with `{group.name}`. Use this for role tokens built on a scale (`space.card.padding` is `{space.md}`). DESIGN.md shows the resolved value, and the script resolves aliases before comparing.
- An undecided value is the string `"TBD"`. Never leave a token out because it is undecided, and never put a guess in.
- Do not add `$description`. The "why" lives in DESIGN.md only, so there is one place to change it.

## Top-level groups and `$type`

Use only these groups, in this order. The script treats a backticked name starting with one of these as a token reference.

| Group | Holds | `$type` | Value format |
|---|---|---|---|
| `color` | All colors, by role | `color` | `#rrggbb`, lowercase. `#rrggbbaa` only if the user wants transparency |
| `font` | `family`, `size`, `weight`, `lineHeight`, `letterSpacing` | `fontFamily`, `dimension`, `fontWeight`, `number`, `dimension` | Family as a string list `"Söhne, Helvetica Neue, Arial, sans-serif"`. Size in `px` or `rem` (pick one for the whole system). Weight as a number like `400`. Line height unitless like `1.5`. Letter spacing in `em` or `px` |
| `typography` | Text styles | `typography` | Object: `fontFamily`, `fontSize`, `fontWeight`, `lineHeight`, `letterSpacing`, each an alias like `"{font.size.md}"` |
| `space` | Spacing scale and gap roles | `dimension` | `px` or `rem` |
| `radius` | Corner radius | `dimension` | `px`, or `9999px` for fully round |
| `border` | `width` and `style` | `dimension`, `strokeStyle` | `1px`, `solid` |
| `shadow` | Shadows, if allowed | `shadow` | A CSS box-shadow string: `"0 1px 2px #0000001a"` |
| `motion` | `duration`, `easing` | `duration`, `cubicBezier` | `150ms`, `"cubic-bezier(0.2, 0, 0, 1)"` as a string |
| `layout` | `grid`, `maxWidth`, `page` | `number`, `dimension` | `12`, `1200px` |
| `breakpoint` | Breakpoints | `dimension` | Min width in `px` |
| `zIndex` | Stacking layers | `number` | Integers like `100` |
| `opacity` | Opacity values, if any | `number` | `0.5` |
| `component` | Tokens that only make sense for one component, like icon sizes or input height | any | as above |

## Naming rules

1. Name by role, not by look. `color.action.primary`, not `color.blue500`. `color.state.error`, not `color.red`. A name should still make sense if the value changes completely.
2. Segments are camelCase, joined with dots: `color.text.onAction`, `font.lineHeight.tight`.
3. Scales use size steps, in this vocabulary and order: `3xs, 2xs, xs, sm, md, lg, xl, 2xl, 3xl, 4xl`. Use only as many as the user decides on. This applies to `space`, `radius`, `font.size`, `shadow`, `breakpoint`.
4. Interactive colors put the state last: `color.action.primary.default`, `.hover`, `.active`, `.disabled`.
5. Text that sits on a colored fill is named for the fill: `color.text.onAction`, `color.text.onError`.
6. Do not create a token the user has not decided on just to complete a pattern. If the user wants only `hover` and not `active`, there is no `active` token, and the component's states table says which token the active state uses.

## Suggested color roles

Offer these as a starting list of roles to fill, not as values. The user removes what they do not need and adds what is missing.

| Role group | Tokens |
|---|---|
| Backgrounds | `color.bg.page`, `color.bg.subtle` |
| Surfaces | `color.surface.default`, `color.surface.raised`, `color.surface.overlay` |
| Text | `color.text.primary`, `color.text.secondary`, `color.text.muted`, `color.text.disabled`, `color.text.inverse`, `color.text.onAction`, `color.text.link` |
| Borders | `color.border.default`, `color.border.strong`, `color.border.subtle` |
| Primary action | `color.action.primary.default`, `.hover`, `.active`, `.disabled` |
| Secondary action | `color.action.secondary.default`, `.hover`, `.active`, `.disabled` |
| States | `color.state.error`, `color.state.errorBg`, `color.state.success`, `color.state.successBg`, `color.state.warning`, `color.state.warningBg`, `color.state.info`, `color.state.infoBg` |
| Focus | `color.focus.ring` |

## Keeping files in sync

Whenever a section is confirmed, edit DESIGN.md and tokens.json in the same step, then run the script. If DESIGN.md shows a value and tokens.json disagrees, DESIGN.md is what the user confirmed, so fix tokens.json.
