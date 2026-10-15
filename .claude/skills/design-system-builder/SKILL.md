---
name: design-system-builder
description: Builds and maintains a design system document by interviewing the user one section at a time, writing DESIGN.md, tokens.json, banned.md, and CHANGELOG.md under design-system/<name>/. Use whenever the user wants to create, start, continue, resume, finish, fill in, review the gaps in, or update a design system, design doc, style guide, design tokens, brand guidelines, or UI guidelines, including changing a single decided value such as a color, font, spacing step, radius, or banned default, or asking what is still missing from one. Not for writing, styling, or reviewing UI code, building components, or applying the design system while coding; a separate skill does that.
---

# Design system builder

Builds a design system document complete and specific enough that an AI building UI later never falls back on its own default choices. A separate enforcement skill reads the output while coding, so the files must follow the fixed structure in the references exactly.

## Core rules

These come first because breaking any of them makes the document useless to the enforcement skill, which trusts every value in it.

1. **Never invent a design value.** If the user has not decided something, write `TBD` and ask. Do not fill gaps with sensible defaults. You may show options to choose from, but nothing is written until the user picks or types a value.
2. **One section at a time.** Ask, wait for the answer, show the written section, get confirmation, then move on.
3. **A few focused questions per turn** (2 to 4). List options as numbered plain text so the user can type an answer. Do not use the AskUserQuestion tool or any other interactive question widget.
4. **Every decision has a short why**, recorded next to it. If a value comes without a reason, ask for the reason once. If the user skips it, write `Why: not given`.
5. **Exact values only**: hex codes, px or rem, ms, font names, numbers. When the user says something vague like "modern", "clean", "subtle", "a bit rounder", ask them to turn it into a concrete value or rule, and offer two or three concrete readings to pick from.
6. **Explain simply.** Assume the user is not a designer. Define a design term in one plain sentence the first time it comes up.
7. **Never use em dashes** in anything you write: the four files, and your messages. Use commas, colons, or full stops.

## Files

Each design system lives in its own folder, `design-system/<name>/`, at the repo root:

| File | What it is | Format |
|---|---|---|
| `DESIGN.md` | Human-readable decisions: values, roles, rules, reasons | [references/doc-template.md](references/doc-template.md) |
| `tokens.json` | Every token in DESIGN.md, and nothing else | [references/tokens-schema.md](references/tokens-schema.md) |
| `banned.md` | Banned AI defaults for this system | [references/doc-template.md](references/doc-template.md), bottom |
| `CHANGELOG.md` | Changes to confirmed decisions | [references/doc-template.md](references/doc-template.md), bottom |
| `examples/` | Optional reference screenshots from section 13 | images |

Section headings, their order, and table column names are fixed. Do not rename, reorder, or drop them, even for a section the user does not care about: write `TBD` or `n/a: <reason>` instead.

## Start of every session

1. List `design-system/`. If there is more than one folder, or the request does not make clear which one, ask which design system you are working on. For a new one, ask for a short folder name (lowercase, hyphens, for example `marketing-site`).
2. Pick the mode:
   - **New**: the folder does not exist. Create all four files with `py .claude/skills/design-system-builder/scripts/check_sync.py init design-system/<name>`. It copies the skeleton from doc-template.md, with every value `TBD` and every skeleton token already in tokens.json as `"TBD"`, so the two files start in sync. Then start the interview at section 1.
   - **Continue**: the folder exists and the user wants to keep going, or the request is unclear. Run the check script (below), read DESIGN.md, and tell the user in a short list which sections are done, which have TBDs, and which are untouched. Resume at the first section in order that is not done, unless the user picks another.
   - **Update**: the user wants to change a decision already made. See Update mode below.

## Interview flow

Go through sections 1 to 13 in order. The question bank for each is in [references/sections.md](references/sections.md); read the part for the current section before asking. For each section:

1. **Ask** one turn of 2 to 4 questions from the bank, skipping anything already answered earlier. Say how many turns this section will take, roughly.
2. **Wait** for the answer. Push back once on vague words or a missing why (rules 4 and 5). If the user says "skip" or "don't know yet", record `TBD` and add it to the Open questions list.
3. **Repeat** until the section's "Must record" list in the bank is covered or explicitly TBD.
4. **Show** the finished section exactly as it will appear in DESIGN.md, plus a short list of the tokens it adds to tokens.json with their values.
5. **Confirm**: ask "Does this look right? Say yes, or tell me what to change." Do not move on without a yes.
6. **Write** on yes: update DESIGN.md and tokens.json in the same step, update Open questions, set `Last updated:` to today, and run the check script to catch sync mistakes right away. Fix anything it reports that you caused, then go to the next section.

Notes that apply across sections:
- Lines in the skeleton that explain how to fill it (like "If dark mode is no, delete the Dark column") are removed once the section is filled.
- For contrast (section 2), never estimate ratios. The check script computes them from tokens.json; copy its numbers into the 2.2 table. For a single pair: `py <skill>/scripts/check_sync.py contrast "#333333" "#ffffff"`.
- If a later answer changes an earlier confirmed section (for example a new color needed by a component), say so, get a yes, update both files, and log it in CHANGELOG.md.
- The user can stop at any point. Run the completion check before ending.

## Update mode

1. Find the decision in DESIGN.md. Show the current value and its recorded why.
2. Ask for the new value and the reason for the change (rule 4 still applies).
3. Find what else depends on it: contrast pairs that use the color, text styles that use the size, component state tables that reference the token, banned.md entries. Tell the user what will change as a result, and ask about any knock-on decision instead of deciding it yourself.
4. Show the updated section, get a yes, then edit DESIGN.md and tokens.json together.
5. Add a row at the top of the CHANGELOG.md table: date (today, YYYY-MM-DD), what changed (token name or rule), old value, new value, why. Filling a `TBD` for the first time is not a change and is not logged.
6. Run the completion check.

## Completion check

At the end of every session, however short, follow [references/final-checklist.md](references/final-checklist.md). In short: run

```
py .claude/skills/design-system-builder/scripts/check_sync.py design-system/<name>
```

(`python` or `python3` if `py` is not available), check the few things the script cannot, and tell the user plainly whether the design system is complete, and if not, exactly what is still missing and where the next session starts.

## References

- [references/sections.md](references/sections.md): questions for each of the 13 sections, and what each must record. Read the current section before asking.
- [references/doc-template.md](references/doc-template.md): the exact DESIGN.md skeleton, plus banned.md and CHANGELOG.md formats. Read when creating files or writing a section.
- [references/tokens-schema.md](references/tokens-schema.md): tokens.json shape, groups, naming rules, suggested color roles. Read before writing any token.
- [references/banned-defaults-starter.md](references/banned-defaults-starter.md): the starter list for section 11.
- [references/final-checklist.md](references/final-checklist.md): the end-of-session check and report format.
- `scripts/check_sync.py`: sync, TBD, why, contrast, and structure checks. Run with `--all` to check every design system.
