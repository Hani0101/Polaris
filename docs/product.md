# Polaris

Polaris guides a learner toward a subject they want to learn. The agent explains in a conversation, draws on a whiteboard, shows an animation, and checks understanding with a quiz. What it knows about the learner is the profile.

## Problem

A person wants to learn a specific topic, including material from a course, in a way that fits them. The explanation has to change for what that person already knows and where they struggle.

## Users

v1 has one learner: the person running Polaris on their own machine. Polaris reaches Claude through that person's Claude login. See [Personal login, local only](decisions/0001-personal-login-local-only.md).

A sign-in page for that learner is required before Sunday 18 Oct 2026, even without hosting. Sign-in is optional: Polaris opens on the app, and only the profile needs it. See [Local sign-in before Sunday](decisions/0004-local-sign-in-before-sunday.md) and [Optional sign-in protects the profile](decisions/0008-optional-sign-in-protects-the-profile.md). Every other item in the MVP scope below is due before that date, so each outranks sign-in when choosing what to build next.

Once Polaris is hosted, it is meant for students, people learning for their work, visual learners, auditory learners, reading and writing learners, kinesthetic learners, people who want a guide, and learners with limited income.

## MVP scope

- Chat, as sessions made of turns. The learner can keep more than one session, reopen any of them, and give each a name.
- Profile, shared across sessions and kept only for a signed-in learner. The teaching agent reads it before every reply in a signed-in session and does not write it. A separate pass writes it when a session ends, from the turns sent while signed in. The learner can also change it in Settings. During a signed-in session with an empty profile, every reply asks and does not teach. The pass design still needs research. See [Profile pass](decisions/0003-profile-pass-is-a-proposal.md) and [An empty profile keeps being asked](decisions/0005-empty-profile-keeps-asking.md).
- Whiteboard, which the agent and the learner can both draw on
- Quiz, graded against a stored answer key. It starts in the chat, and the learner can expand it onto its own page.
- Animation. A later long-running job uses the same notice rules as animation (AN-02, AN-03, AN-07, AN-08).
- Flashcards, a deck for revision. Every card is tied to a source in the session's turns or resources, and a deck is checked by code before it is stored. See [Flashcards](features/flashcards.md) and [A deck's sources are checked by code](decisions/0012-deck-sources-checked-by-code.md).
- Artifacts: a stored whiteboard, quiz, animation, or flashcard deck, reopened from the session that created it
- Resources: PDFs, Word documents, text files, typed notes, images, and web pages added by their link that the learner gives a session, which the agent explains from and cites. See [Resources](features/resources.md).
- Web mode, a toggle in the chat input. Only a message sent with it on lets the agent search and read public web pages, and the reply links what it used. See [Chat](features/chat.md) and [The web is used only on request](decisions/0013-web-only-on-request-and-public.md).
- Settings, a menu at the bottom of the left panel with two items, each opening a dialog: the appearance mode (System, Light, or Dark), kept in the browser, and the profile, where a signed-in learner sees what Polaris knows about them and changes it. See [Settings](features/settings.md) and [The learner can edit the profile](decisions/0014-the-learner-can-edit-the-profile.md).

Success for this scope is a correct explanation, an animation that plays, a quiz whose score matches the stored key, and evals that pass.

## UX

- Meets WCAG AA
- Mobile first
- Structured replies
- Honest about limits
- Inputs in v1 are typed chat, drawing on the whiteboard, comments on the whiteboard, resources the learner adds to a session, and the web when the learner turns on web mode

## Not in v1

- Hosting the application
- Google OAuth, an accounts server, and more than one learner
- Calling Claude with an API key
- Extra backend copies, a load balancer, and extra Manim workers
- A video cache, cloud video storage, and a per-learner rate limit
- A full review against the OWASP top 10 for LLMs, and guardrails beyond the rules below

## Security

v1 security is four rules already written: the browser never receives the key of a question before that question is checked (QZ-03), grading is done in code (QZ-04), no agent-written animation code runs (AN-04), and Polaris reads only public web pages, never an address on the learner's machine or network (CH-26, RS-23). See [An animation is data, not code](decisions/0006-animation-is-data-not-code.md) and [The web is used only on request](decisions/0013-web-only-on-request-and-public.md).

## Limits

v1 uses Claude only. The agent layer is the Claude Agent SDK, and the machine already has a Claude login. Quality, price, and outages follow that one vendor, and the learner cannot pick a model.

A later version should let the learner choose a cheaper model or a more expensive one. Revisit this limit before adding a second model. Claude-only is the v1 rule, not the permanent shape.
