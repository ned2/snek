# Fix the logical grid once; terminal resizes change only the cell scale

Decided 2026-08-27 (issues 0007, 0029, 0030).

The board has two independent sizes. The *logical grid* is the game's width and height in cells:
it is model state, it holds the snake and food coordinates, and it sets the difficulty (how much
room there is, and how long the snake must grow to fill it). The *cell scale* (k) is purely
visual: one cell is drawn `2k` columns by `k` rows, so cells look square. The sizing mode
(`sizing_mode`) picks both from the space available. `cap` grows the grid with the terminal up to
`max_grid_*`, then enlarges cells up to `cell_scale`, giving a consistently sized board that may
be letterboxed. `fill` fixes cells at `cell_scale` and grows the grid to fill the terminal, so
board size and difficulty vary with the window. Both floor the grid at `min_game_*`.

The grid is established once, from `SnakeView`'s first valid layout while the game is still
fresh. After that a terminal resize only refits the scale (`fit_grid_scale`), never below one, and
never touches the model. Previously `Game.resize()` scaled each snake segment and the food
independently, which could collapse segments onto one cell, break the body's adjacency, or put
food on the snake. Fixing the grid preserves the snake, food, queued turns, score and demo
strategy state by construction, and a resize can never change difficulty mid-game. A terminal too
small for the board at scale one clips the drawing (below the supported 80×24) but leaves the
game intact.

## Considered options

- Scale every coordinate onto the new grid: cannot keep the snake valid, so rejected.
- Rebuild a valid snake and food placement on the new grid: needs a fallback for a grid too small
  for the snake, and would still let a resize change difficulty mid-game.

## Consequences

- There is no model API for changing dimensions: `Game.resize()` was removed, and the grid changes
  only through a reset before play begins.
- Later games reuse the established grid, so enlarging the window between games does not enlarge a
  `fill` board. Since 2026-09-26 a new game re-establishes the grid only if a layout setting (sizing
  mode, cell scale, grid cap, walls or food type) changed on the settings screen.
- Speed comes from the scale the grid was established at, not the scale currently drawn, so a resize
  never changes speed either.
- Sprite food tightens these rules: see [ADR 0010](0010-sprite-food-scale-and-size-hold.md).
