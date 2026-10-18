# Polaris docs

These docs are the language and the rules for Polaris. Read them before changing the product.

## How to use them

1. Use [the glossary](glossary.md) for the meaning of a word. If a word is not listed, it is not a Polaris term yet.
2. Use [the product](product.md) for who v1 is for, what is in scope, and what is later.
3. Use [decisions](decisions/) for a choice that should stay put, and why.
4. Use the feature page for the rules of that feature. Each rule has an id. A scenario names the rule it checks.
5. Use [research](research/) for findings that propose a change. A research note changes no rule or decision until that change is accepted.

- [Chat](features/chat.md)
- [Profile](features/profile.md). PR-01 through PR-08 are in force. The session-end writer is accepted so it can run. The pass design still needs research; see [decision 0003](decisions/0003-profile-pass-is-a-proposal.md). During a session with an empty profile, every reply still asks and does not teach ([decision 0005](decisions/0005-empty-profile-keeps-asking.md)).
- [Whiteboard](features/whiteboard.md). New drawings are one format version; see [decision 0006](decisions/0006-one-drawing-format-version.md).
- [Resources](features/resources.md). Material the learner adds to a session for the agent to explain from and cite. The agent reads it and never writes it.
- [Quiz](features/quiz.md)
- [Animation](features/animation.md). A new animation is data that Polaris plays, not code ([decision 0006](decisions/0006-animation-is-data-not-code.md)). On `feat/animation`, a small evaluation sends maths and heavy graphs to Manim and everything else to Lottie (AN-21). Both engines come from experiments that [decision 0006](decisions/0006-animation-is-data-not-code.md) has not yet accepted; see [the Lottie experiment](experiments/lottie-animation.md) and [the Manim research](research/0003-manim-experiment.md).
- [Auth](features/auth.md). Sign-in is optional and protects the profile only ([decision 0008](decisions/0008-optional-sign-in-protects-the-profile.md)).
- [Settings](features/settings.md). The Appearance mode (System, Light, Dark) is kept in the browser ([decision 0010](decisions/0010-appearance-mode-stays-in-the-browser.md)).
- [Research: profile design](research/0001-profile-design.md). Proposed, not in force. Compares profile designs and drafts [decision 0006](decisions/0006-typed-profile-with-evidence.md) and new PR rules.
- [Research: Manim experiment](research/0003-manim-experiment.md). An experiment, now used on `feat/animation` for maths and heavy graphs. It runs agent-written code, which AN-04 forbids.

When a feature page and the glossary disagree, the glossary wins on meaning and the feature page wins on behavior.
