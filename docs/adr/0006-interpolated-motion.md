# Interpolate movement, with the drawing one step behind the model

Decided 2026-09-24 (issue 0027); kept after turn-lag testing, 2026-09-26 to 2026-10-01 (issue 0036).

The snake moves one logical cell per step, and a cell is big on screen: `2*scale` columns by
`scale` rows, where the cell scale is how many terminal characters draw one cell. With whole cells
the head appeared and the tail vanished a block at a time, which read as judder. The view now
slides the snake between cells, with the drawing trailing the model by up to one step.
`Game.step()` reports the new head, the vacated tail cell and their directions in `StepResult`, and
`rendering.motion_cells()` turns those and the step clock's progress into part-filled cells. A step
is drawn in `2*scale` equal increments: whole columns across, `▀`/`▄` half rows vertically, which
are the same physical size on a 2:1 cell. The head cell fills from the side it entered as the
vacated cell drains, so the visible length stays constant, and the first increment shows as soon
as the step is taken. Because it trails, the drawing never shows a move the model has not made.

Since 2026-10-04 the snake is drawn in pixels finer than a character
([ADR 0012](0012-snake-narrower-than-its-cells.md)), and a step is drawn in one increment a pixel
across the cell (`2*scale` with half blocks, `4*scale` with sextants or octants). A partly drawn
cell is the whole cell's pixels clipped from the side it fills from. Sextant pixels are not square,
with fewer down a cell than across it, so a step down rounds each increment to the nearest pixel.
Each end of the snake moves one pixel an increment, the gap included: the head's join into its new
cell is the old head's gap when moving right or down, so that cell (the neck) fills its gap first,
and the tail's join likewise sits in the new tail cell when moving left or up, which empties its gap
last. A partly drawn cell can therefore carry several clips, one from each end of a short snake.
Clipping only the head and vacated cells instead stalls the head for a gap's worth of increments
and then jumps it, which reads as a late response to a key.

Cells are drawn whole unless all of these hold: `smooth_motion` is on (`--no-smooth` turns it off);
the empty glyph is the default blank, since the unfilled part of a partial cell is blank; a step
spans at least two frames, since faster steps would show a few unevenly timed
increments; and exactly one step ran in the wake, since several mean the loop fell behind. Game
over settles the board whole.

## Considered options

- **Predicting ahead and correcting**: it rubber-bands when the player turns mid-step.
- **Interpolating only the head**: the body's length pulses.
- **A smaller default cell scale**: changes the look and the difficulty.
- **Textual's `animate` or `auto_refresh`**: they couple badly to the step timing.
- **Fixes for turn lag** (issue 0036). A key takes effect at the next step, and until then the
  trailing head keeps sliding straight to finish its cell, so at slow speeds with big cells turns
  felt late. Play-testing rejected drawing ahead of the model and swinging round on a key (the tip
  jumps sideways), committing to the next move from halfway through a step (a latency cliff and two
  possible corner cells), hurrying the clock so the turn comes within about 50 ms (it changes the
  pace), rushing only the drawing to the corner and waiting there (a stutter), and no smoothing at
  slow speeds (big whole-cell jumps). A one-column lead at cell scale 4 was adopted on 2026-09-27
  and removed on 2026-10-01: no mode used scale 4 any more, and at scale 3 it swung visibly. Turn
  lag is bounded by speed instead: moves per second never fall below a floor
  ([ADR 0008](0008-worlds-as-nokia-levels.md)).

## Consequences

- The loop wakes at every increment boundary rather than once a step
  ([ADR 0004](0004-exact-deadline-step-timing.md)), which costs two to three times the CPU of
  `--no-smooth`.
- Progress a hair short of an increment boundary counts as on it, matching the wake scheduled there.
  Without that tolerance, float rounding draws the old increment at that wake and two at the next.
