---
status: accepted
---

# Appearance mode stays in the browser

Polaris has a Light and a Dark palette in the design system. Until now the app picked one from the operating system and gave the learner no say. The learner can now choose System, Light, or Dark in Settings (ST-02).

The choice is kept in the browser, under one key, and nowhere else. It is not sent to the server and not tied to sign-in. Sign-in is optional ([decision 0008](0008-optional-sign-in-protects-the-profile.md)) and protects the profile only, and the mode is something the learner wants before they have signed in, including on a first visit. The profile is what Polaris knows about the learner, not how the screen looks, so the mode does not belong there either.

The cost is that the mode follows the browser, not the learner. A second browser starts on System. Syncing the mode to a signed-in learner is parked in `later.md`.

The app applies the mode with a `data-theme` attribute on the page root. A short script in the page head sets it from the stored choice before the first paint (ST-06). System sets no attribute, and the operating system's setting decides.

Two things do not follow the mode, on purpose:

- A whiteboard keeps the colors it was made with. The mode decides only the color of a board made afterwards (WB-22). Recoloring a board would change what the learner drew.
- A finished video animation keeps its colors (AN-22). Its colors are fixed when it is rendered, so it cannot follow the mode, and saying so is better than half following it.
