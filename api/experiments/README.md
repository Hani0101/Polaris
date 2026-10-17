# Manim experiment (`feat/manim-experiment`)

This branch makes animations with Manim instead of Polaris animation data. It
runs agent-written code, which AN-04 and decision 0006 forbid, so it stays on
this branch until that is decided. The findings are in
`docs/research/0002-manim-experiment.md`.

## Install

`uv sync` in `api/`. On Windows and macOS every package has a wheel. On Linux,
`manimpango` and `pycairo` build from source and need the Pango and Cairo
headers (`apt install libpango1.0-dev libcairo2-dev pkg-config`). No LaTeX and
no FFmpeg install is needed: maths uses Typst and video uses PyAV.

## Run the app with Manim

Manim is the default writer on this branch. `POLARIS_ANIMATION_ENGINE=data`
brings back the animation-data writer.

## Run the briefs

```
cd api
uv run python -m experiments.run_manim --out ../experiments-out/round [--brief pendulum] [--model opus] [--previews 0]
uv run python -m experiments.summarize ../experiments-out/round
```

Each brief calls Claude through the local login. A brief costs about $0.10
to $0.55 and takes one to four minutes.
