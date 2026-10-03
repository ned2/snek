# Draw the board with the Line API from snapshots

Decided 2026-09-23 (issue 0027).

`SnakeView` used to be a `Static` that rendered the whole board and was centred by CSS, and every
move rewrote the whole view: about 17 KB a move at 200x50, even with same-style cells merged into
one segment. That much output risks tearing on terminals without synchronized output. Refreshing
only some regions of a `Static` would not have helped much: Textual re-runs its whole `render()`
for any dirty region, and the widget cannot tell where CSS alignment put the board.

`SnakeView` is now a plain `Widget` using Textual's Line API. `render_line()` centres and frames
the board itself and draws each board row with the pure `rendering.render_board_row()`. Lines are
drawn from `BoardState`, a frozen snapshot of what the board shows (snake cells, food, world, food
symbol and any part-drawn cells), not from the live `Game`. `update_board()` takes a new snapshot,
compares it with the one on screen and refreshes only the regions of cells that differ, so Textual
re-renders only those lines and writes only those cells. At 200x50 the median output per move fell
to about 1 KB and CPU use from 10.5% to 6.5%, which also left room to redraw interpolated movement
at up to 60 updates a second.

## Consequences

- The drawing can differ from the live game until the view is told. After model steps call
  `update_board()`; after a reset or a direct edit of the model, call a full `refresh()`, which
  drops the snapshot so the next render draws the live game whole.
- Whatever changes how a cell is drawn must either be in `BoardState`, so the comparison sees it,
  or force a full refresh. Otherwise Textual's cached lines go stale.
- Centring, the frame and the LCD bezel are the widget's job, not CSS's.
- Tests compare Textual's cached lines with a fresh full render after demo play, with and without
  interpolation, to catch a missed region.
