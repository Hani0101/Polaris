---
status: proposed
---

# An animation is data, not code

## Context

Until now the animation writer returned a Python script. The sandbox ran that script, and the script wrote `animation.html`. The learner's browser then ran the JavaScript inside that page, in an iframe with a content security policy.

That spent the safety and retry effort on the wrong code:

- The Python only wrote a string. The code the learner actually ran was the JavaScript in the page, which never ran in the sandbox. The browser was already the real safety boundary. The Python sandbox is an audit hook, and audit hooks are not a sandbox (PEP 578). Its own docstring lists the holes.
- A job was ready when the script exited cleanly and a file existed. A JavaScript error, an empty picture, overlapping captions, or sideways scroll at 320px all passed. The three runs in AN-05 only caught Python errors.
- Colours, fonts, step controls, and reduced motion depended on the model following the prompt. Stored animations used colours and fonts outside the design system.
- The rest of Polaris could not see inside an animation. It had no description, a later turn could not know what it showed, and the learner could not point at a part of it.

## Decision

A new animation is data. The writer returns animation data in the Polaris animation format. The backend checks that data in code before it is stored, and Polaris's own player draws it.

- No agent-written code runs for a new animation, not in the sandbox and not in the browser. AN-04 now says that.
- The Python sandbox is no longer used. It is removed from the code.
- The check errors are what AN-05 sends back to the writer. They name the step and the element, for example "step 3 moves 'ball' off the canvas".
- The player owns the step controls, the captions, the colours, the fonts, and reduced motion. The data names colours by role and cannot pick a font.
- A finished animation stores a description, so a screen reader can read it and a later turn can see it.
- Animations that a job already finished as `animation.html`, `.mp4`, `.webm`, or `.gif` still open the way they did (AN-06). Nothing new is written in those forms.

The animation format is its own format, not a whiteboard. It reuses the whiteboard's checks for math, code, and graphs, and the same way of plotting a function on the backend. A whiteboard does not gain a timeline. WB-07 (replay step by step) stays parked.

## Alternatives

- **Keep Python, add a headless-browser check.** Catches JavaScript errors and blank pages. Leaves style, accessibility, and the description to the model, and keeps running code nobody needs.
- **The agent writes HTML, checked in a headless browser.** Chromium with no network and a time limit becomes the sandbox. Same gaps as above, and adds Chromium to the learner's machine.
- **Polaris owns the page shell, the agent writes the motion as JavaScript.** Fixes style. Still runs agent code, and Polaris still cannot see inside it.
- **Manim.** Strong for maths. Needs FFmpeg and maybe LaTeX on Windows, long renders, native code that the sandbox cannot isolate, and a fixed video that cannot offer a step mode for reduced motion.
- **Remotion, Lottie.** Remotion's player in a product that generates videos needs a paid licence. Lottie is too low-level for a model to write well.

## Consequences

- Animations are less expressive than free JavaScript. The evals show which briefs cannot be expressed. An escape hatch is not added before that.
- Claude's structured output does not accept every JSON Schema feature. The schema sent to the writer is checked against the SDK docs, and the backend check stays the authority.
- The playback content security policy also blocks WebRTC (`webrtc 'block'`) for older HTML animations. Browsers may not enforce it yet.
- The product's security line changes from "animation code runs only in the sandbox" to "no agent-written animation code runs".
