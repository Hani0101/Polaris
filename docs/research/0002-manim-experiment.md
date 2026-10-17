---
status: experiment
date: 2026-10-17
branch: feat/manim-experiment
---

# Research: animations made with Manim

The learner asked for richer animations than the Polaris animation format can draw. This note records an experiment on the `feat/manim-experiment` branch: the writer writes a Manim Community scene, Polaris renders it to video, and the learner watches it step by step.

Nothing here is in force. The branch runs code that the writer wrote, which AN-04 and [decision 0006](../decisions/0006-animation-is-data-not-code.md) forbid. It is not merged into `development`.

## 1. What the branch does

| Part | Where | What it does |
|---|---|---|
| Writer | `api/polaris/manim_writer.py` | One Agent SDK `query()` per draft. Its system prompt is a Manim style guide for teaching. It has one tool, `render_preview`. It returns `{title, description, code}` through structured output. |
| Preview tool | `manim_writer.py` `render_preview` | Renders the scene at 640x480, 15 fps. Returns the check errors, layout advice, and for each step a strip of frames from inside the step and the step's last frame. At most five previews. |
| Scene helpers | `api/polaris/manim_assets/polaris_manim.py` | `PolarisScene` with `self.step(caption)`. Design-system colours (dark mode) and text sizes. |
| Runner | `api/polaris/manim_assets/manim_child.py` | Runs one scene in its own process. Uses a 4:3 frame (like the Polaris canvas), the design-system fonts, and Typst instead of LaTeX. Checks the layout after every animation and writes one clip per step. |
| Render | `api/polaris/manim_render.py` | Static checks on the code, then the runner with a time limit, a stripped environment, and an audit hook. |
| Job | `api/polaris/manim_job.py` | Write, final render (1440x1080, 60 fps), at most two fixes (AN-05, AN-09). It stores the video, the step clips, a last-frame picture for each step, WebVTT captions, and `manim.json`. |
| Player | `web/src/animation/VideoStepPlayer.tsx` | Plays one clip per step, with the same controls, captions, step buttons, narration, and "Ask about this step" as the Polaris player. Under reduced motion it shows each step's last frame. |

The check after every animation refuses a scene when:

- something leaves the frame,
- two pieces of text touch,
- text is smaller than size 40 (about 14px on a 320px phone),
- text is dimmed below 50% opacity,
- an animation runs before the first step,
- a step is shorter than half a second, or
- the scene has more than 10 steps or runs longer than 150 seconds.

Layout advice does not refuse a scene. It covers a small or off-centre picture at the end of a step, and a line that runs through a label.

## 2. How it was tested

The ten animation eval briefs (`api/evals/animation_briefs.json`) were run four times through the real writer, with the Claude login on this machine. `api/experiments/run_manim.py` runs them, and `api/experiments/summarize.py` makes the tables.

| Round | Model | Preview tool | Guide and checks |
|---|---|---|---|
| 1 | Sonnet 5.5 | on | first version, text size 32 |
| 2 | Sonnet 5.5 | on | text size 40, Typst matched to text, faint-text check, picture-size advice, frames from inside each step |
| 3 | Sonnet 5.5 | off: the writer returns code once, and render errors come back as fixes | same as round 2 |
| 4 | Opus 5.5 | on | same as round 2; stopped after five briefs |

## 3. Results

| Round | Ready | Ready on the first run | Cost per brief | Time per brief | Final render |
|---|---|---|---|---|---|
| 1 | 10/10 | 10 | $0.24 | 117 s | 29 to 68 s |
| 2 | 10/10 | 10 | $0.30 | 118 s | 28 to 48 s |
| 3 (no previews) | 10/10 | 7 | $0.11 | 95 s | 23 to 67 s |
| 4 (Opus, 5 briefs) | 5/5 | 5 | $0.24 | 113 s | 29 to 56 s |

The videos are 22 to 39 seconds long, with 4 to 7 steps. Each video file is 0.5 to 0.8 MB of H.264.

What the frames showed:

- **The facts were right in every round.** 100 × 1.1⁵ = 161.05, the derivative of x² is 2x, binary search found 23 in three checks, and bubble sort moved 5 to the end.
- **Round 1 drew too small.** Pictures sat in the top half, and text at size 32 was about 10px on a phone. Round 2's size rules and picture-size advice fixed this.
- **Without previews, mistakes reach the learner.** Round 3 had three visible defects in ten videos: two fractions drawn on top of each other, a grey disc covering the unit circle, and a tangent line running past its axes. Round 2 had none of these. The touching-text check now refuses the first one; the other two can only be seen.
- **The writer uses what it sees.** In rounds 1 and 2, the writer changed its scene after a preview with no errors in 7 of 10 briefs: it fixed things it saw in the frames, not things a check reported.
- **Opus explained a little more** (why each bubble-sort swap happens, labels on each part of the attention mix) at the same cost. Five briefs are too few to choose a model.

## 4. Problems found on the way

- LaTeX is not on the learner's machine. Manim's numbers and axis labels use LaTeX by default. The runner switches them to Text, and the writer uses Typst for maths. Typst came out about 0.7 times the size of Text at the same font size, so the runner scales it up.
- Text boxes in Manim fit the glyphs closely, so any touch between two of them is a real collision.
- The headless Chromium used for the browser check cannot play H.264. Chrome, Edge, Safari, and Firefox can. The player was checked here with VP9 copies of the clips.
- The first write check compared path prefixes as strings, so `out` also allowed writes to `outside.npy`. A test found it, and it now compares real paths.

## 5. What this means for Polaris

- **Install.** On Windows every package has a wheel, so `uv sync` is enough. No LaTeX or FFmpeg is needed. Linux needs the Pango and Cairo headers.
- **Security.** This is the open question. The audit hook and the static checks are not a sandbox: native code can get past them (PEP 578). Shipping agent-written Manim code needs isolation from the operating system, such as a container with no network. On a learner's Windows laptop that is heavy. Decision 0006 would have to change, and the security line in [product.md](../product.md) with it.
- **Rules kept.** AN-01 to AN-03, AN-05 to AN-09, AN-12, AN-13, AN-15 to AN-20. AN-14 holds through dark-mode colours and the design-system font, but the video does not follow a light theme.
- **Rules broken.** AN-04 (agent code runs). AN-10 and AN-11 are checked on the rendered scene, not on data.
- **Cost and time.** About $0.30 and two minutes per animation, with previews. Without previews it is about $0.11, but some defects get through.

## 6. Recommendation

If Manim is adopted, keep the preview tool, the layout checks, and the style guide as they are on this branch. Do not ship it to more than one learner until the code runs in real isolation.

The other path is the one in [the earlier comparison](../decisions/0006-animation-is-data-not-code.md): keep animation data and have Polaris turn it into a Manim scene with its own code. That keeps AN-04 and loses the writer's freedom, which is what made these videos richer than the data format.
