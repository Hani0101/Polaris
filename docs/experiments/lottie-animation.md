# Experiment: animations as Lottie videos

Branch `feat/lottie-experiment`. Not merged. This experiment sets aside decision 0006's
"Lottie is too low-level for a model to write well" to find out whether that is still true
when the writer can see its own frames.

## How it works

- An animation is a **Lottie video**: 1 to 12 Lottie scenes played one after another. Each scene
  is one step and has a caption. The data is stored as `animation.json` with `"format": "lottie"`
  (`api/polaris/lottie_video.py`).
- The **writer** (`api/polaris/lottie_writer.py`) is a Claude agent with no built-in tools. An
  in-process MCP server gives it `write_scene`, `edit_scene`, `read_scene`, `delete_scene`,
  `preview_scene`, `set_video` and `check_video`. `preview_scene` draws frames in headless
  Chromium with lottie-web (`scripts/render-lottie.mjs`) and returns them as an image, so the
  writer looks at overlaps, cropping and timing and fixes them before it finishes.
- The writer's system prompt carries the motion and design guides from the `text-to-lottie`
  skill (https://github.com/diffusionstudio/lottie, MIT), copied into
  `api/polaris/lottie_guides/`, plus a known-good starter scene and Polaris's palette and fonts.
- The **check** refuses expressions (lottie-web would run them as JavaScript), image layers,
  external files, fonts other than Atkinson Hyperlegible, text smaller than 30 units, the wrong
  canvas (800 × 600), and scenes outside 1.5 to 20 seconds. When Node and a Chromium-family
  browser are present, it also renders every scene and refuses scenes that throw or end blank.
  The AN-05 fix loop is unchanged.
- The **player** (`web/src/animation/LottiePlayer.tsx`) uses lottie-web's light SVG build,
  which has no expression support. Scenes run on into each other like one video. Back, Next,
  Replay, Pause, step dots, a progress bar per scene, captions, narration, "Ask about this
  step", and reduced motion (each scene's last frame) all work.

## Running it

- The app uses the Lottie writer by default on this branch. `POLARIS_ANIMATION_WRITER=format`
  switches back to the old writer. `POLARIS_ANIMATION_MODEL` picks the writer's model.
- To run one eval brief: `api/.venv/Scripts/python.exe api/evals/run_lottie_one.py pendulum`.
  It writes `api/evals/results/lottie/<brief>/animation.json`, and the writer's scenes, previews
  and `transcript.log` go under `api/evals/results/lottie/lottie-work/<brief>/`.
- To watch a result without the backend: start the web dev server and open
  `/dev/lottie?src=/@fs/E:/Polaris/api/evals/results/lottie/pendulum/animation.json`.

## What this gives up

- Colours are fixed in the Lottie data, so the video keeps a paper background in dark mode.
- Polaris checks structure and renders frames, but it cannot check overlap or the canvas edge
  the way the format check could. The writer's own visual review covers that.
- A job takes several minutes and costs more than the old one-shot writer.
