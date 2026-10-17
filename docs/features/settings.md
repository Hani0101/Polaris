# Settings

Settings is a page of choices about how Polaris looks and behaves for this learner on this browser. In v1 it has one section, Appearance. Later sections (the agent's memory of the learner, sign-in) are parked in `later.md`.

The appearance mode is how the app picks light or dark colors. See [Appearance mode stays in the browser](../decisions/0010-appearance-mode-stays-in-the-browser.md).

## Rules

ST-01  The learner can open Settings from the left panel, on every screen size. A Back control returns them to the screen they came from.
ST-02  Settings has an Appearance section with three choices: System, Light, and Dark. Exactly one is chosen.
ST-03  System follows the operating system's light or dark setting and changes with it while Polaris is open. Light and Dark ignore the operating system.
ST-04  The first time the app opens in a browser, the mode is System.
ST-05  The chosen mode is kept in the browser and applies at once, with no reload. It is not sent to the server and not tied to sign-in.
ST-06  The mode is applied before the first paint, so the learner never sees the other mode flash on load.
ST-07  If the browser cannot keep the choice, the app still works and uses System.
ST-08  The mode changes every color in the app from the design system's Light or Dark column, including code blocks in replies and the whiteboard's own menus and toolbar.
ST-09  Switching the mode never changes a whiteboard that exists. It decides only the color of a board made after the switch (WB-22).
ST-10  A finished video animation keeps its own colors in either mode (AN-22).
ST-11  Settings fits a phone from 320px wide with no horizontal scroll, every control is at least 44px, and it is reachable and usable by keyboard and screen reader (WCAG AA). The choices are a group with a name, and the chosen one is announced.

## Scenarios

Scenario: Settings opens from the left panel  [ST-01]
  Given the learner is in a chat
  When they choose Settings in the left panel
  Then the Settings page is showing
  And Back returns them to that chat

Scenario: Settings offers three modes  [ST-02]
  Given the Settings page is showing
  When the learner looks at Appearance
  Then it offers System, Light, and Dark
  And exactly one is chosen

Scenario: System follows the operating system  [ST-03]
  Given the mode is System and the operating system is set to dark
  When the operating system changes to light while Polaris is open
  Then the app changes to light colors without a reload

Scenario: Light ignores the operating system  [ST-03]
  Given the learner chose Light and the operating system is set to dark
  When the app opens
  Then the app uses light colors

Scenario: a new browser starts on System  [ST-04]
  Given nothing is stored in the browser
  When the app opens
  Then Appearance shows System as chosen

Scenario: the choice is kept in the browser  [ST-05]
  Given the learner chose Dark
  When they reload the page
  Then the app is dark and Appearance shows Dark as chosen
  And no request to the server carried the choice

Scenario: no flash on load  [ST-06]
  Given the learner chose Dark and the operating system is set to light
  When the page loads
  Then the first paint is dark
  And no light page shows first

Scenario: a browser that cannot keep the choice still works  [ST-07]
  Given the browser refuses to store the choice
  When the learner opens the app
  Then the app opens using System
  And choosing another mode still changes the colors for that visit

Scenario: every part follows the mode  [ST-08]
  Given the learner chose Light
  When they look at the chat, a code block in a reply, a quiz, and the whiteboard toolbar
  Then each uses the design system's Light colors
  And text keeps the contrast ratios in the design system (WCAG AA)

Scenario: an open whiteboard keeps its colors  [ST-09, WB-22]
  Given a whiteboard is open on the white board color
  When the learner switches the mode to Dark
  Then that whiteboard and its marks do not change
  And a whiteboard made after the switch opens on the night board color

Scenario: a finished video stays dark  [ST-10, AN-22]
  Given a finished video animation made with dark colors
  When the learner switches to Light
  Then the video looks the same as before

Scenario: Settings fits a phone  [ST-11]
  Given a phone screen 320px wide
  When the learner opens Settings
  Then the page and its controls fit without horizontal scroll
  And every control is at least 44px

Scenario: a screen reader hears the choice  [ST-11]
  Given a screen reader is on the Settings page
  When it reaches Appearance
  Then it reads the group's name and which choice is chosen
