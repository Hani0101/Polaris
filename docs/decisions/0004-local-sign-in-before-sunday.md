---
status: accepted, superseded in part by [0008](0008-optional-sign-in-protects-the-profile.md)
---

# Local sign-in before Sunday

Decision 0008 replaces the idea that this page gates the whole app, and the "no sign-in before that Sunday" rule. Sign-in is optional and protects the profile only. The deadline below still stands.

Polaris needs a sign-in page for its one learner before Sunday 18 Oct 2026, while it still runs on one machine. That page is not Google OAuth and not an accounts server. Those stay with the hosted version. Until the page exists, and only before that Sunday, the app opens with no sign-in.

The page asks for a username and a password. The learner chooses that pair the first time the page is used. Both are stored on the machine, for the one learner. There is no accounts server behind them. v1 has no way to replace a forgotten pair.

This gate is not the Claude login. Decision 0001 is how Polaris reaches Claude. This page is how the learner opens Polaris.
