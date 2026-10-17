# Polaris docs

These docs are the language and the rules for Polaris. Read them before changing the product.

## How to use them

1. Use [the glossary](glossary.md) for the meaning of a word. If a word is not listed, it is not a Polaris term yet.
2. Use [the product](product.md) for who v1 is for, what is in scope, and what is later.
3. Use [decisions](decisions/) for a choice that should stay put, and why.
4. Use the feature page for the rules of that feature. Each rule has an id. A scenario names the rule it checks.

- [Chat](features/chat.md)
- [Profile](features/profile.md). PR-01 through PR-08 are in force. The session-end writer is accepted so it can run. The pass design still needs research; see [decision 0003](decisions/0003-profile-pass-is-a-proposal.md). During a session with an empty profile, every reply still asks and does not teach ([decision 0005](decisions/0005-empty-profile-keeps-asking.md)).
- [Whiteboard](features/whiteboard.md). New drawings are one format version; see [decision 0006](decisions/0006-one-drawing-format-version.md).
- [Quiz](features/quiz.md)
- [Animation](features/animation.md). A new animation is data that Polaris plays, not code ([decision 0006](decisions/0006-animation-is-data-not-code.md)).
- [Auth](features/auth.md)
- [Research: profile design](research/0001-profile-design.md). Proposed, not in force. Compares profile designs and drafts [decision 0006](decisions/0006-typed-profile-with-evidence.md) and new PR rules.
- [Research: Manim experiment](research/0002-manim-experiment.md). An experiment on the `feat/manim-experiment` branch, not in force. It runs agent-written code, which AN-04 forbids.

When a feature page and the glossary disagree, the glossary wins on meaning and the feature page wins on behavior.
