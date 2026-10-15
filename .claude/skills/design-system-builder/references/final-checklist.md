# Completion check

Run this at the end of every session, even a short one, and before saying a design system is done.

## 1. Run the script

```
py .claude/skills/design-system-builder/scripts/check_sync.py design-system/<name>
```

Use `python` or `python3` instead of `py` if that is what the machine has. The script checks:

- all four files exist
- every `##` section from the template is present, in order
- every token in a DESIGN.md table exists in tokens.json, and every token in tokens.json appears in a DESIGN.md table
- every backticked token reference in DESIGN.md exists in tokens.json
- values match between the two files (after resolving `{aliases}`)
- every row in a table with a `Why` column has a why, and every bullet under a "Rules" heading has `Why:`
- the contrast pairs in section 2.2, with ratios and AA pass or fail for light and dark
- banned.md has at least one entry, and the gap rule is set
- every remaining `TBD`, with file and line
- any em dash in the four files

It exits with code 0 only when nothing is missing.

## 2. Check what the script cannot

Read DESIGN.md once more and look for:

- **Vague words left in a value or rule**: modern, clean, subtle, minimal, sleek, soft, nice, friendly, slightly, a bit, some. Each must be a number, a token, or a concrete rule.
- **Components missing a state.** Every component has all eight states, or `n/a: <reason>`.
- **Values the user did not give.** If you are unsure whether a value came from the user, ask. A value you invented is worse than a TBD.
- **Contrast failures the user has not accepted.** A failing pair needs either a fix or a rule in 2.3 saying it was kept on purpose, with why.
- **Open questions list** matches the actual TBDs.

## 3. Report to the user

Use this shape, in plain words:

```
Design system: <name>
Status: Complete / Not complete

Still to decide (<count>):
- 2. Colors: dark mode value for color.state.warning
- 7. Components: loading state for Table
...

Sync between DESIGN.md and tokens.json: OK / <problems>
Missing reasons: none / <list>
Contrast: all pass / <failing pairs>
banned.md: OK / missing
Gap rule: <value> / not set

Next time we start from: <section>
```

Set `Status: Complete` at the top of DESIGN.md only when the script exits 0 and step 2 found nothing. Otherwise keep `Status: In progress`. Update `Last updated:` to today either way.
