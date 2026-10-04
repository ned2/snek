# Draw the snake narrower than its cells, in pixels finer than a character

Decided 2026-10-04 (issue 0042).

Every snake cell used to be a solid block, so a snake doubling back one row from itself drew as one
slab and its path could not be read. On the Nokia 6110 a cell is 4 pixels square and the snake 3
pixels wide: consecutive segments join, but runs lying side by side keep a 1-pixel gap. Snek now
draws the snake the same way in every mode. Each snake cell is a grid of *pixels* finer than a
terminal character, lit but for a gap of a quarter of the cell (Nokia's ratio, rounded, at least one
pixel) along its right and bottom edges. A cell fills one of those gaps only where it *joins* the
next or previous segment across it. Joins are worked out from the snake's order, not from which
cells touch, and across a wrapping edge too.

The pixels come from Unicode block glyphs, chosen by the **snake glyphs** setting
(`snake_glyphs`): *sextants* (2×3 pixels a character, Unicode 13, the default), *octants* (2×4,
Unicode 16) or *half blocks* (1×2, `▀▄█`). A cell at scale k is 2k characters by k, so it holds 4k×3k
sextant pixels, 4k×4k octant pixels or 2k×2k half-block pixels. Octants at scale 1 and half blocks
at scale 2 are exactly Nokia's 4×4 cell. Which glyphs a terminal can draw depends on its font and
cannot be detected, so it is the player's choice, defaulting to sextants: they look much like
octants but have been drawn by more terminals for longer. Half blocks work everywhere, but at scale
1 they leave the snake only half a cell wide.

## Considered options

- **Quadrants** (`▘▝▖▗…`, 2×2 a character): drawn everywhere, but at scale 1 vertical runs come out
  half as thick again as horizontal ones.
- **A bigger cell scale for Classic** (half blocks at scale 2 are Nokia's cell): the board no longer
  fits 80×24 with the side panel, so cap sizing would drop to scale 1 there anyway, and moves a
  second would halve, since pace is speed on screen
  ([ADR 0008](0008-worlds-as-nokia-levels.md)).
- **Telling runs apart by colour** (alternating shades): the LCD palette has only two tones.
- **Inset every cell, joined or not**: simpler, but breaks the body into beads, and Nokia's snake is
  one piece.

## Consequences

- The board snapshot records each snake cell's joins, not just which cells hold the snake
  ([ADR 0005](0005-line-api-board-snapshots.md)). Each step changes four cells rather than two: the
  old head gains a join and the new tail loses one.
- Smooth motion clips a cell's pixels from the side it fills from, in pixel increments
  ([ADR 0006](0006-interpolated-motion.md)). The vacated tail cell keeps its join to the new tail
  while it drains, or a gap would open a frame early. Joins and gaps move a pixel an increment
  like the rest of the snake, so the neck or the new tail is clipped too in some directions.
- The snake is no longer a tiled glyph, so the `snake_block` setting is gone.
- The setting is part of every mode with the same value, like smooth motion, so choosing other
  glyphs shows the mode as Custom.
