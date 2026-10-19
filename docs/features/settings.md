# Settings

Settings is a menu of choices about how Polaris looks and behaves for this learner. It opens upward from the Settings button at the bottom of the left panel. In v1 it has two items, Appearance and Profile, and each opens a dialog. A sign-in item is parked in `later.md`.

The appearance mode is how the app picks light or dark colors. See [Appearance mode stays in the browser](../decisions/0010-appearance-mode-stays-in-the-browser.md).

The Profile dialog shows what Polaris knows about the learner and lets them change it (PR-11). Unlike the mode, it lives on the server and needs sign-in (AU-12). See [The learner can edit the profile](../decisions/0014-the-learner-can-edit-the-profile.md).

## Rules

ST-01  The Settings button sits at the bottom of the left panel, on every screen size. It opens a menu upward with Appearance and Profile, and each item opens its own dialog over the screen the learner is on. Settings is not a page. A dialog's choices apply at once, so it has only a Close button. Closing returns focus to the Settings button.
ST-02  The Appearance dialog has three choices: System, Light, and Dark. Exactly one is chosen.
ST-03  System follows the operating system's light or dark setting and changes with it while Polaris is open. Light and Dark ignore the operating system.
ST-04  The first time the app opens in a browser, the mode is System.
ST-05  The chosen mode is kept in the browser and applies at once, with no reload. It is not sent to the server and not tied to sign-in.
ST-06  The mode is applied before the first paint, so the learner never sees the other mode flash on load.
ST-07  If the browser cannot keep the choice, the app still works and uses System.
ST-08  The mode changes every color in the app from the design system's Light or Dark column, including code blocks in replies and the whiteboard's own menus and toolbar.
ST-09  Switching the mode never changes a whiteboard that exists. It decides only the color of a board made after the switch (WB-22).
ST-10  A finished video animation keeps its own colors in either mode (AN-22).
ST-11  The Settings menu and both dialogs fit a phone from 320px wide with no horizontal scroll, every control is at least 44px, and they are reachable and usable by keyboard and screen reader (WCAG AA). The appearance choices are a group with a name, and the chosen one is announced.
ST-12  The Profile dialog loads the profile each time it opens. For a signed-in learner it lists every fact on the profile as a bullet point, under a heading for its kind, in the order the agent reads them. A kind with no fact shows no heading.
ST-13  A learner who is not signed in sees no facts, only a sentence that the profile needs sign-in and a Sign in button that opens the sign-in page (AU-02).
ST-14  Each fact has a Change and a Remove control. Change turns the bullet into a text field holding the fact, with Save change and Cancel. Escape cancels. After saving or cancelling, focus returns to that fact's Change control.
ST-15  Remove asks first in a confirm dialog over the Profile dialog, naming the fact. Nothing is removed until the learner confirms. Afterwards focus is on the add field.
ST-16  Below the list, a text field adds a fact. A fact is one line of at most 300 characters. A blank fact, or one the profile already holds, is refused with a message under the field, and nothing is stored.
ST-17  The dialog says that Polaris reads the profile before every reply, so a change applies from the next message. A saved change is announced to screen readers.
ST-18  An empty profile shows an empty state that says the profile fills when the learner leaves a session, with the add field below it. A profile that fails to load shows an error with Try again.

## Scenarios

Scenario: Settings opens a menu upward  [ST-01]
  Given the learner is in a chat
  When they choose Settings at the bottom of the left panel
  Then a menu opens above the button with Appearance and Profile
  And the chat stays where it was

Scenario: each Settings item opens a dialog  [ST-01]
  Given the Settings menu is open
  When the learner chooses Appearance
  Then the Appearance dialog opens over the chat
  And Close returns focus to the Settings button

Scenario: Settings offers three modes  [ST-02]
  Given the Appearance dialog is open
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
  When the learner opens the Settings menu, then the Profile dialog
  Then the menu, the dialog, and their controls fit without horizontal scroll
  And every control is at least 44px

Scenario: a screen reader hears the choice  [ST-11]
  Given a screen reader is in the Appearance dialog
  When it reaches the choices
  Then it reads the group's name and which choice is chosen

Scenario: the profile is listed as bullet points  [ST-12]
  Given a signed-in learner whose profile says they like worked examples and struggle with fractions
  When they open Profile from the Settings menu
  Then "likes worked examples" is a bullet under "How you like to be taught"
  And "struggles with fractions" is a bullet under "Where you find it hard"

Scenario: a signed-out learner is asked to sign in  [ST-13]
  Given the learner is not signed in
  When they open Profile from the Settings menu
  Then the Profile dialog shows no facts
  And Sign in opens the sign-in page

Scenario: a fact is changed in place  [ST-14, PR-11]
  Given the Profile dialog lists "struggles with fractions"
  When the learner chooses Change, types "finds fractions hard", and chooses Save change
  Then the bullet reads "finds fractions hard"
  And focus is on its Change control
  And the next reply is written with "finds fractions hard" in hand

Scenario: a fact is removed after a confirmation  [ST-15, PR-11]
  Given the Profile dialog lists "likes videos"
  When the learner chooses Remove
  Then a dialog asks "Remove this from your profile?" and names the fact
  And the fact is removed only after they choose Remove from profile

Scenario: a repeated fact is refused  [ST-16]
  Given the profile already says "likes worked examples"
  When the learner adds "Likes worked examples."
  Then the field says "Your profile already says this."
  And the profile still holds that fact once
