# Animation

An animation is a moving explanation. In v1, a job is one request to produce an animation. A later long-running job follows AN-02, AN-03, AN-07, and AN-08. The finished animation is an artifact of the session that asked for it.

## Rules

AN-01  The job id comes back before the animation is ready, and the chat stays usable.
AN-02  The chat tells the learner the animation may take some time, that they can keep talking in this session or another, and that the operating system will notify them when it is ready.
AN-03  When the job finishes, the operating system notifies the learner that the animation is ready, including when they are in another session or another application. Opening the notice shows that animation.
AN-04  Agent-written animation code runs only inside the sandbox, with no network and a time limit.
AN-05  On failure, the error goes back to the agent. The agent may submit a fix at most twice, for three runs in total.
AN-09  After those runs have failed, the session that started the job is told that Polaris cannot create the animation right now and that the learner should try later. The operating system does not send a ready notice. A later request may start a new job.
AN-06  A finished animation is stored as an artifact of the session that requested it. The learner can open it again from that session.
AN-07  The operating-system permission prompt appears when a long-running job starts, and only if a notice is needed and the operating system does not already have an answer. It does not appear when the app opens.
AN-08  If the learner refuses that permission, the finished job still appears in the session that started it, and no notice is sent.

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

Scenario: the sandbox runs the code  [AN-04]
  Given the agent wrote animation code
  When the job runs
  Then the code runs in the sandbox with no network and a time limit

Scenario: two fixes then stop  [AN-05, AN-09]
  Given the first run and two fixes have failed
  When the job fails again
  Then no further fix is run
  And that session is told Polaris cannot create the animation right now and to try later
  And no ready notice is sent
