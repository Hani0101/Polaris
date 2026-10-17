# Live evals

Opt-in evals that call the real teaching agent, profile pass and animation writer through the Claude login on this machine, then score the output in code. The unit tests in `api/tests/` mock the model; these do not. They cost money and take minutes, so `pytest` does not collect them (`testpaths = ["tests"]`).

## Run

From `api/`:

```
uv run python -m evals
```

Options:

- `--runs N`: samples per case (default 3)
- `--cases pr02-first,wb-math`: run only these cases (default all)
- `--jobs J`: samples run at once (default 3)
- `--list`: list the cases and the rules each checks

The run stops if `ANTHROPIC_API_KEY` is set or the CLI reports any API-key credential (decision 0001).

The report is written to `api/evals/reports/<timestamp>.md`, with the raw results beside it as `.json`. That folder is gitignored.

## Isolation

Each sample gets its own temporary data dir with its own `profile.json` and `polaris.db`. It is deleted afterwards. The learner's real `api/data/` (or `POLARIS_DATA`) is never opened. Teaching cases run a real `Chat` with no profile pass and no animation writer bound, so a turn cannot write the profile or start a background job.

## Cases

| Case | Rules | What it checks |
|---|---|---|
| `pr02-first` | PR-02 | Empty profile: the reply asks for the missing profile, calls no tools, and does not give the derivative it was asked for |
| `pr02-again` | PR-02, PR-04 | Same, on the second reply of that session (decision 0005); the profile is still empty |
| `pr01-struggle` | PR-01, PR-03 | Profile names a fraction struggle; the slope reply adapts to it (**model judge**) and does not ask for the profile again |
| `wb-steps` | WB-05, WB-06 | First `draw_whiteboard` call passes `check_drawing`; every stored step's `[[step:<id>]]` marker is in the reply |
| `wb-math` | WB-05, WB-06, WB-12 | Quadratic formula is a `math` element; the whole formula is not written as a text element or freehand |
| `wb-graph` | WB-05, WB-06, WB-13 | `y = x^2 - 4` is a `graph` element, not freehand |
| `quiz` | QZ-05, QZ-10 | First `create_quiz` call is accepted by the stored-quiz checks; the stored input re-passes `normalize_spec` |
| `an-brief` | AN-04 | The `start_animation_job` brief contains no code |
| `an-writer` | AN-04, AN-10 | The writer's first animation data, from a fixed brief, passes the animation check |
| `pr08-exact` | PR-08 | Profile pass on a session that repeats "I suck at math" sends UPDATE or IGNORE, never a second ADD |
| `pr08-reworded` | PR-08 | Same, with a reworded repeat |

## Scoring

Every check is code except the one marked **model judge**: a single Haiku-class call with a fixed yes/no schema, used only where adapting to a struggle cannot be checked in code. The report labels it.

Some code checks are keyword heuristics (asking for the three profile parts, "does not teach", "a second ADD" of a reworded fact, code in a brief). They say so in their names or in this table. Read the transcript in the report before trusting a failure.

A check that does not apply to a sample (no whiteboard drawn, so no step markers) counts as n/a, not as a pass or a fail. The pass rate is passed / (passed + failed).

## Adding a case

Add an async function `(data_dir, sample)` to `cases.py` that records checks with `sample.check(name, ok, detail)`, then add a `Case` to `CASES` with the rule ids it checks.
