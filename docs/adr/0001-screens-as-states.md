# Screens as states on the Textual screen stack

Decided 2025-08-19 (no issue; commit c3abb38); fresh modal instances 2026-06-13 (issue 0004).

Each state of the UI (splash, playing, paused, diagnostics, settings, game over) is a Textual
screen, and the current state is whichever screen is on top of Textual's screen stack. Moving
between states is `push_screen` / `pop_screen`, and overlays such as pause are `ModalScreen`s
pushed over the game, which stays beneath them. This replaced an early `StateManager` with its own
states and transition table, which the app consulted in a single key handler while mounting and
unmounting views by hand. That duplicated what Textual already tracks (which screen is active,
what lies beneath it, and each screen's key bindings and focus), and gave two sources of truth
that could disagree. The stack is the only one.

Splash, game and pause are registered screens (`SnakeApp.SCREENS`): Textual creates each once and
reuses it. Settings, diagnostics and game over are pushed as fresh instances every time, because
each shows a snapshot built when it is composed: while game over was a registered screen it kept
showing the first game's banner and score.

## Consequences

- The registered `GameScreen` and the app's `Game` outlive a game, and `on_mount` runs only once.
  Starting a game must reset both (`GameScreen.start_new_game()`), and leaving one must stop its
  loop. ESC is the one way back to the splash, from the game and from each modal over it, and it
  goes through `GameScreen.leave_to_menu()`, which leaves the game paused so nothing restarts the
  step timer behind the splash.
- A new screen that shows changing state should either be pushed fresh or refresh itself when it
  resumes, as the splash does for the mode the settings screen may have changed.
