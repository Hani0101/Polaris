# Polaris docs

These docs are the language and the rules for Polaris. Read them before changing the product.

## How to use them

1. Use [the glossary](glossary.md) for the meaning of a word. If a word is not listed, it is not a Polaris term yet.
2. Use [the product](product.md) for who v1 is for, what is in scope, and what is later.
3. Use [decisions](decisions/) for a choice that should stay put, and why.
4. Use the feature page for the rules of that feature. Each rule has an id. A scenario names the rule it checks.

- [Chat](features/chat.md)
- [Profile](features/profile.md). PR-02 is accepted. Writing the profile (PR-05 to PR-08) is proposed. Refuse to build that writing while [decision 0003](decisions/0003-profile-pass-is-a-proposal.md) stays proposed. Until a writer exists, an empty profile is asked for on every reply ([decision 0005](decisions/0005-empty-profile-keeps-asking.md)).
- [Whiteboard](features/whiteboard.md)
- [Quiz](features/quiz.md)
- [Animation](features/animation.md)
- [Auth](features/auth.md)

When a feature page and the glossary disagree, the glossary wins on meaning and the feature page wins on behavior.
