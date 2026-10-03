# `StepResult` as the model-to-view contract

Decided 2026-06-13 (issue 0002).

`Game.step()` advances the model by one step (one cell of movement) and returns a frozen
`StepResult` that says what the step meant: whether the snake moved, ate food, changed world (and
to which), or ended the game. The game screen reacts to those flags, for example by switching the
theme on a world change or pushing the game-over screen, rather than working out what happened by
comparing the snake's length or the world index before and after the step, as it used to. That
put game rules in the view and meant the model could not be tested without a Textual app. Now the
model alone decides the consequences of a step, and they are tested on a plain `Game`.

## Considered options

- **Textual messages from the model.** Only Textual's message pumps (apps, screens and widgets)
  can post messages, so a plain `Game` cannot, and making it one would tie the model to Textual.
  A returned value suits a single caller that acts on the result at once; messages remain the
  tool for when another widget or screen must react.

## Consequences

- A new consequence of a step belongs in `StepResult`, not in view code that infers it. The
  result has since grown the fields that interpolated drawing needs: the new head, the vacated
  tail cell and the direction each moved in.
- Timers, themes and screens stay in the view, driven by the result. Speed is not a flag: the
  view reads the model's current step interval before every step.
