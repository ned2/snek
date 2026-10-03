# Classic plays like Nokia Snake, and `GameConfig`'s defaults are Classic's

Decided 2026-09-26 (issues 0030, 0031); the LCD palette was added the same day (issue 0033) and
narrowed to the board on 2026-10-01 (issue 0039).

Classic is Snek's default mode, and it plays as close to the original Nokia Snake (Nokia 6110,
1997–98) as a terminal allows. That is not Snake II (Nokia 3310), which most descriptions mix in:
the original has solid walls rather than wraparound, and no bonus items. So Classic has a walled
20×11 board, one diamond-shaped food at a time, a snake that starts 8 cells long, a fixed world
(Nokia's level, see [ADR 0008](0008-worlds-as-nokia-levels.md)) and a board drawn like the
green-grey LCD. The board size comes from a reconstruction of the phone's screen, and the starting
length is inferred from Nokia's published maximum score: 212 foods fill the 220-cell board. Solid
walls began as an option (issue 0028) and became the default with Classic. Nokia's crash grace, a
moment before a crash in which a turn can still save the snake, is not adopted.

`GameConfig`'s defaults are Classic's values. A bare `GameConfig()` is then the game a player gets
with no flags, and since the mode in force is derived from the settings (see
[ADR 0007](0007-modes-derived-from-settings.md)), a session opens on Classic, the first mode in
`MODES`, rather than on Custom.

**Grow-in.** Nokia-style, the snake starts as a single cell, at the centre of the board heading
right, and unrolls to `start_length`: for `Game.pending_growth` more steps its tail stays put, as
if it had eaten. Food eaten meanwhile grows it as usual, so its length is always the starting
length plus the foods eaten. A single cell fits on any board, and the body is always a path the
head has taken, so no starting shape has to be fitted to the board or kept clear of its walls.

**The LCD palette** (`palette = "lcd"`) draws only the board and its frame as the Nokia screen.
`LCD_BOARD_STYLE`, dark pixels on the backlight, is applied beneath each cell's own style: the
snake, the diamond and the frame take the LCD tones, while glyph food keeps its world's colour and
sprites keep their pixels. Everything around the board (the margin, side panel, splash and modals)
takes the world's theme under either palette.

## Considered options

- **A starting length of 10** (one first-hand account, which also gives a different maximum score)
  **or 3** (fan sites): both contradict the 212-food figure, so 8 stays until better evidence turns
  up.
- **The LCD palette as a theme for the whole app** (until 2026-10-01): it looked right on the board
  but poor on the splash and menus.

## Consequences

- Model tests that depend on what Classic leaves out must opt out explicitly: `walls=False` for a
  wrapping board, `world_change="progress"` for progression, and `start_length=1` for a one-cell
  snake with no grow-in. When the defaults became Classic's, tests written for the old wrapping
  board silently became walled.
- During grow-in the tail does not leave its cell, so the collision check and the demo strategies
  must treat it as occupied (`demo/_helpers`). Assigning `game.snake` directly clears grow-in.
- Changing one of Classic's values means changing the matching `GameConfig` default too.
