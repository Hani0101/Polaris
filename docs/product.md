# Polaris

Polaris guides a learner toward a subject they want to learn. The agent explains in a conversation, draws on a whiteboard, shows an animation, and checks understanding with a quiz. What it knows about the learner is the profile.

## Problem

A person wants to learn a specific topic, including material from a course, in a way that fits them. The explanation has to change for what that person already knows and where they struggle.

## Users

v1 has one learner: the person running Polaris on their own machine. Polaris reaches Claude through that person's Claude login. See [Personal login, local only](decisions/0001-personal-login-local-only.md).

A sign-in page for that learner is required before Sunday 18 Oct 2026, even without hosting. See [Local sign-in before Sunday](decisions/0004-local-sign-in-before-sunday.md).

Once Polaris is hosted, it is meant for students, people learning for their work, visual learners, auditory learners, reading and writing learners, kinesthetic learners, people who want a guide, and learners with limited income.

## MVP scope

- Chat, as sessions made of turns. The learner can keep more than one session and reopen any of them.
- Profile, shared across sessions. The teaching agent reads it before every reply and does not write it. An empty profile is asked for on every reply until a writer exists, because nothing stores the answer. Writing it is a proposal. See [Profile pass is a proposal](decisions/0003-profile-pass-is-a-proposal.md) and [An empty profile keeps being asked](decisions/0005-empty-profile-keeps-asking.md).
- Whiteboard, which the agent and the learner can both draw on
- Quiz, graded against a stored answer key. It starts in the chat, and the learner can expand it onto its own page.
- Animation. A later long-running job uses the same notice rules as animation (AN-02, AN-03, AN-07, AN-08).
- Artifacts: a stored whiteboard, quiz, or animation, reopened from the session that created it

Success for this scope is a correct explanation, an animation that plays, a quiz whose score matches the stored key, and evals that pass.

## UX

- Meets WCAG AA
- Mobile first
- Structured replies
- Honest about limits
- Inputs in v1 are typed chat, drawing on the whiteboard, and comments on the whiteboard

## Not in v1

- Hosting the application
- Google OAuth, an accounts server, and more than one learner
- Calling Claude with an API key
- Extra backend copies, a load balancer, and extra Manim workers
- A video cache, cloud video storage, and a per-learner rate limit
- A full review against the OWASP top 10 for LLMs, and guardrails beyond the rules below

## Security

v1 security is three rules already written: the browser never receives the answer key (QZ-03), grading is done in code (QZ-04), and animation code runs only in the sandbox (AN-04).

## Limits

v1 uses Claude only. The agent layer is the Claude Agent SDK, and the machine already has a Claude login. Quality, price, and outages follow that one vendor, and the learner cannot pick a model.

A later version should let the learner choose a cheaper model or a more expensive one. Revisit this limit before adding a second model. Claude-only is the v1 rule, not the permanent shape.
