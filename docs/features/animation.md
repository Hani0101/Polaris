# Animation

An animation is a moving explanation. In v1, a job is one request to produce an animation. A later long-running job follows AN-02, AN-03, AN-07, and AN-08. The finished animation is an artifact of the session that asked for it.

A new animation is data that Polaris plays, not code. See [An animation is data, not code](../decisions/0006-animation-is-data-not-code.md).

## Rules

AN-01  The job id comes back before the animation is ready, and the chat stays usable.
AN-02  The chat tells the learner the animation may take some time, that they can keep talking in this session or another, and that the operating system will notify them when it is ready.
AN-03  When the job finishes, the operating system notifies the learner that the animation is ready, including when they are in another session or another application. Opening the notice shows that animation.
AN-04  No agent-written code runs for an animation. The writer returns animation data, and Polaris's player draws it.
AN-05  On failure, the error goes back to the agent. The agent may submit a fix at most twice, for three runs in total.
AN-09  After those runs have failed, the session that started the job is told that Polaris cannot create the animation right now and that the learner should try later. The operating system does not send a ready notice. A later request may start a new job.
AN-06  A finished animation is stored as an artifact of the session that requested it. The learner can open it again from that session.
AN-07  The operating-system permission prompt appears when a long-running job starts, and only if a notice is needed and the operating system does not already have an answer. It does not appear when the app opens.
AN-08  If the learner refuses that permission, the finished job still appears in the session that started it, and no notice is sent.
AN-10  The backend checks the animation data before it is stored. Data that fails the check is not stored or drawn, and the run counts as a failed run under AN-05. Each error names the step and the element it is about.
AN-11  The check refuses an animation where, at any moment, an element is outside the canvas, two pieces of text overlap, or text is smaller than the minimum size. It also refuses an action on an element that does not exist, a timing outside the limits, and a caption that is too long.
AN-12  The animation plays in steps, and every step has a caption. The learner can play, pause, go back a step, go to the next step, and replay the current step. Step dots show which step they are on.
AN-13  When the learner's system asks for reduced motion, the animation does not move on its own. Each step shows its finished picture, and the learner moves with Back and Next. The steps and captions are the same.
AN-14  Text uses the design system's fonts. The design system's colours are the default, not a limit: when the subject is better shown in other colours, or on another background, the writer may choose them. Text and thin lines keep a contrast of at least 4.5:1 with what is behind them (WCAG AA). In the animation format, the data names a colour by its role and does not choose a font.
AN-15  Every animation has a text description that a screen reader can read (WCAG AA). When the step changes, a screen reader announces the new caption.
AN-16  A later turn in the session can see what each finished animation showed, step by step.
AN-17  The learner can ask about the step they are on. The next turn knows which animation and which step was asked about.
AN-18  The learner can turn on narration, which reads each caption aloud with a voice on their own machine. It is off until they turn it on, and the captions stay on screen.
AN-19  While a job runs, the learner can see which stage it is in: writing, checking, or fixing.
AN-20  The animation fits a phone screen from 320px wide, with no horizontal scroll, and every control is at least a 44px tap target.
AN-21  Before the writer starts, a small evaluation reads the learner's message and the brief and picks the engine: Manim for a maths problem or a heavy graph, Lottie for everything else. If the evaluation fails, a keyword check picks. Routing never fails a job.
AN-22  A video animation made by Manim keeps its own colors in Light and in Dark, since they are fixed when it is rendered. A data animation follows the appearance mode through its color roles (AN-14).

## Engines

On `feat/animation` a job is written by one of two writers. `api/polaris/animation_router.py` picks it (AN-21).

- **Manim** (`api/polaris/manim_writer.py`) for maths and heavy graphs: equations, calculus, geometry, trigonometry, linear algebra, proofs, plots of functions or data on axes, and graph theory with many nodes and edges. See [the Manim research](../research/0003-manim-experiment.md).
- **Lottie** (`api/polaris/lottie_writer.py`) for everything else: how something works, processes, systems, stories, timelines, and simple diagrams and charts. See [the Lottie experiment](../experiments/lottie-animation.md).

The evaluation is one structured-output call to a small model (`claude-haiku-5-5`, or `POLARIS_ROUTER_MODEL`) with no tools. It sees the learner's message from the turn that started the job and the teaching agent's brief, and returns `manim` or `lottie` with a reason. The choice is kept in the job's folder as `route.json`.

`POLARIS_ANIMATION_ENGINE` set to `manim`, `lottie`, or `data` makes every job use that one writer. Unset, or `auto`, uses the router.

Colours (AN-14): both writers start from the design system's palette and may leave it. The Lottie writer sets a background with its `set_background` tool, and the player paints it. A Manim scene sets `self.camera.background_color`.

## The animation format

The animation schema is the Pydantic models in `api/polaris/animation_format.py`. `check_animation` in that module checks animation data before it is stored. `describe_animation` builds the text a later turn reads, and `readable_animation_description` builds the text a screen reader reads.

An animation has a `version` (1), an `id`, a `title`, a `description`, a list of `elements`, and a list of `steps`. The canvas is 400 units wide and 300 high. The player scales it to the width it has.

An element has an `id`, a `kind`, a position, and a colour role. Its kinds are `rectangle`, `ellipse`, `line`, `arrow`, `path`, `text`, `math`, `code`, and `graph`. Math, code, and graph elements use the same checks as the whiteboard (WB-12, WB-13). A graph's points are plotted on the backend and the browser does not evaluate the expression. An element is hidden until a step shows it, unless it is marked visible at the start.

A colour role is one of `ink`, `muted`, `accent`, `positive`, `negative`, and `highlight`. The player maps each role to a design-system token, so the same animation follows the theme. Text uses the design system's font.

A step has an `id`, a `caption`, a duration, and a list of actions. An action names one element and has a start time and a duration inside the step. The actions are:

- `appear` and `disappear`, with a fade.
- `move` to a position.
- `follow` a path: a list of points, or `x(t)` and `y(t)` expressions over a range of `t`. Expressions are sampled on the backend with the whiteboard's expression rules, and the browser draws the sampled points.
- `trace`, which draws a line, a path, an arrow, or a graph series from its start to its end.
- `highlight`, which changes the element's colour role for the rest of the step or the rest of the animation.
- `count`, which changes a number in a text element from one value to another.
- `scale`, which resizes an element around its centre.

The check works out where every element is at the end of each step and along every `move` and `follow`. It uses those positions for the canvas and overlap rules in AN-11. The limits on counts, sizes, durations, and caption length are in `AnimationLimits` in the same module. Text is at least 22 units high. On a 320px phone screen the canvas is about 254px wide, so that text is about 14px.

Step playback ends at the last step. Replay starts the current step again from the picture at the end of the step before it. Back shows the picture at the end of the step before.

The writer returns this data through structured output. The backend check, not the schema sent to the writer, decides what is accepted.

### Stored animations

A ready job stores `animation.json` in its work folder, and the media route serves it. A job that finished before this format stored `animation.html`, `animation.mp4`, `animation.webm`, or `animation.gif`. Those still open as before: video and images in the browser's player, HTML in a sandboxed iframe with no network. Nothing new is written in those forms.

### The rest of the session

The prompt for a later turn lists each ready animation in the session with `describe_animation`: its title, its description, and each step's caption with the elements that step shows or moves.

The "Ask about this step" action sends the turn with the animation id and the step id as metadata on the turn, in the same way pointing works on the whiteboard (WB-08). That turn's prompt names the animation, the step number, and the step's caption.

### Job stages

A running job has a `stage`: `writing` for the first run, `checking` while the backend checks the data, and `fixing` while the writer works on a fix. The job's status is still `running`, `ready`, or `failed`. A ready or failed job has no stage.

### Narration

Narration uses the browser's speech synthesis with voices marked as local only, so it works offline and sends no text off the machine. When no local voice exists, the narration control is not shown. Narration reads the caption when a step starts, and stops when the learner pauses or changes step.

## Scenarios

Scenario: the chat stays usable  [AN-01, AN-02]
  Given the learner asked for an animation
  When the job is still running
  Then the chat tells them it may take some time
  And they can send another message in this session or open another session

Scenario: the operating system notifies the learner  [AN-02, AN-03]
  Given a job is running and the learner was told the operating system will notify them
  When the job finishes while the learner is in another application
  Then the operating system shows a notice that the animation is ready
  And opening that notice shows the animation

Scenario: a refused permission still delivers the animation  [AN-08]
  Given the learner refused notification permission
  When the animation job finishes
  Then no notice is sent
  And the animation appears in the session that started the job

Scenario: permission is asked when the job starts  [AN-07]
  Given the operating system has not been asked for notification permission
  When the learner opens the app
  Then no permission prompt appears
  And when a long-running job then starts, the prompt appears

Scenario: no agent code runs  [AN-04]
  Given the agent started an animation job
  When the job produces the animation
  Then the writer returns animation data
  And no code from the writer is run on the machine or in the browser

Scenario: two fixes then stop  [AN-05, AN-09]
  Given the first run and two fixes have failed
  When the job fails again
  Then no further fix is run
  And that session is told Polaris cannot create the animation right now and to try later
  And no ready notice is sent

Scenario: a refused check goes back to the writer  [AN-05, AN-10]
  Given the writer returned animation data where step 3 moves "ball" past the right edge
  When the backend checks it
  Then the data is not stored
  And the writer receives an error that names step 3 and "ball"
  And the writer's next answer is the first fix

Scenario: the check finds layout problems  [AN-11]
  Given animation data where two captions on the canvas overlap at the end of a step
  When the backend checks it
  Then the check refuses it and names both elements and the step

Scenario: the learner moves through the steps  [AN-12]
  Given a finished animation with four steps
  When the learner pauses on step 2 and presses Next
  Then step 3 plays and its caption is shown
  And the step dots show step 3

Scenario: reduced motion shows the same steps without movement  [AN-13]
  Given the learner's system asks for reduced motion
  When they open an animation
  Then nothing moves
  And they see the finished picture of step 1 with its caption
  And Next shows the finished picture of step 2

Scenario: the animation uses the design system  [AN-14]
  Given animation data that names the accent role for an element
  When the player draws it
  Then the element uses the design system's accent colour
  And all text uses the design system's font

Scenario: an animation may use its own colours  [AN-14]
  Given a Lottie writer that chose a dark blue background for a night sky
  When the learner opens the animation
  Then the player paints that background behind every scene
  And the text on it keeps a contrast of at least 4.5:1

Scenario: a video keeps its colors in Light  [AN-22]
  Given a finished Manim video with a dark background
  When the appearance mode is Light
  Then the video plays with the same dark background
  And its captions and controls use the Light colors

Scenario: maths goes to Manim, the rest to Lottie  [AN-21]
  Given the learner asked "Show me the derivative as the slope of a tangent"
  When the job starts
  Then the evaluation picks Manim
  And when the learner asks "How does the heart pump blood?", the evaluation picks Lottie
  And if the evaluation call fails, a keyword check picks and the job still runs

Scenario: a screen reader follows the animation  [AN-15]
  Given a finished animation
  When a screen reader reaches it
  Then it reads the animation's description
  And when the step changes, it announces the new caption

Scenario: a later turn knows what the animation showed  [AN-16]
  Given a finished animation in the session
  When the learner asks a question in a later turn
  Then the prompt for that turn lists the animation's title and each step's caption

Scenario: the learner asks about a step  [AN-17]
  Given the learner is on step 3 of an animation
  When they choose "Ask about this step" and send a question
  Then the reply is about step 3 of that animation

Scenario: narration reads the captions  [AN-18]
  Given the learner's machine has a local voice
  When they turn on narration and play the animation
  Then each step's caption is read aloud
  And the caption stays on screen

Scenario: the job shows its stage  [AN-19]
  Given a job whose first run failed the check
  When the learner looks at the animation card
  Then it shows that the animation is being fixed

Scenario: the animation fits a phone  [AN-20]
  Given a phone screen 320px wide
  When the learner opens an animation
  Then the whole canvas and the controls fit without horizontal scroll
  And every control is at least 44px

## Evals

A fixed set of about ten briefs is the animation eval, for example a pendulum, binary search, attention in a transformer, and the derivative as a slope. Each eval run starts a job for every brief with the real writer and records whether it became ready, how many runs it used, and how long it took. The briefs are in `api/evals/animation_briefs.json` and `api/evals/run_animation_evals.py` runs them. The evals call Claude, so they run by hand and not with the unit tests. A report goes to `api/evals/results/`, which is not committed.

## Kept for later

- One check question after the learner watches an animation, since an animation can feel understood when it is not. Polaris already has quizzes for this.
- Interactive controls inside the animation, such as sliders.
- Tying animation steps to the reply text, as WB-06 does for the whiteboard. An animation is ready after the reply that asked for it has finished.

## Open questions

- Which briefs the format cannot express. The evals answer this before any escape hatch is added.
- The overlap check estimates text size from its length and font size. Math and code are measured the same way, so a very wide formula may pass the check and still look crowded.
