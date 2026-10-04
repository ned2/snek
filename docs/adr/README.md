# Architecture decision records

Each file here records one design decision: what was decided and why, so that a later reader
does not undo something deliberate. They describe the reasons behind the code; the code and its
docstrings describe what it does, and [README.md](../../README.md) describes how the game plays.

| ADR | Decision |
|---|---|
| [0001](0001-screens-as-states.md) | Screens as states on the Textual screen stack |
| [0002](0002-stepresult-model-view-contract.md) | `StepResult` as the model-to-view contract |
| [0003](0003-logical-grid-and-cell-scale.md) | Fix the logical grid once; resizes change only the cell scale |
| [0004](0004-exact-deadline-step-timing.md) | Wake the game loop at each step's exact deadline |
| [0005](0005-line-api-board-snapshots.md) | Draw the board with the Line API from snapshots |
| [0006](0006-interpolated-motion.md) | Interpolate movement, with the drawing one step behind the model |
| [0007](0007-modes-derived-from-settings.md) | Modes are derived from the settings, edited as a validated draft |
| [0008](0008-worlds-as-nokia-levels.md) | Worlds are Nokia Snake's levels, and the only source of speed |
| [0009](0009-classic-follows-nokia-snake.md) | Classic plays like Nokia Snake; `GameConfig`'s defaults are Classic's |
| [0010](0010-sprite-food-scale-and-size-hold.md) | Sprite food needs cell scale 2; a too-small terminal holds the game |
| [0011](0011-make-lifecycle-interface.md) | Make is the development lifecycle interface |
| [0012](0012-snake-narrower-than-its-cells.md) | Draw the snake narrower than its cells, in pixels finer than a character |

## When to write one

Write an ADR for a decision that is all three of:

- **hard to reverse**: changing course later would cost real work;
- **surprising without context**: a reader of the code would wonder why it is done this way;
- **the result of a real trade-off**: there were genuine alternatives, chosen between for reasons.

A decision that fails any of these needs no ADR.

## Format

Name the file `NNNN-short-slug.md`, numbered one past the highest here, and add it to the table
above. Keep it short: an ADR can be a single paragraph.

```md
# Short title of the decision

Decided YYYY-MM-DD (issue NNNN).

What the context was, what was decided, and why.

## Considered options

## Consequences
```

- The date is when the decision was made. A later amendment is dated in the text.
- The issue number is provenance only. The project's issue tracker is local and not part of the
  repository, so an ADR must read on its own without it; omit the number when there is none.
- Include **Considered options** only when a rejected alternative is worth remembering, and
  **Consequences** only when an effect downstream is not obvious.
- Define a project term the first time an ADR relies on it.
- To reverse a decision, write a new ADR and mark the old one at its top:
  `Superseded by [ADR NNNN](NNNN-slug.md).` Amend an ADR in place only to record a refinement of
  the same decision.
