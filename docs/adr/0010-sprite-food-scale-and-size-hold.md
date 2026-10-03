# Sprite food needs cell scale 2; a too-small terminal holds the game

Decided 2026-09-26 (issue 0030).

Food can be drawn as pixel-art sprites (`food_type` "sprites"). A sprite needs a cell scale (the
number of terminal characters per board cell, k) of at least `MIN_SPRITE_SCALE`, which is 2: at
scale one a cell is only 2×1 characters. The view used to fall back to a glyph whenever the scale
came out as one, so whether a player saw sprites depended on their terminal's size at the start,
and a game could switch from sprites to glyphs when the window shrank. We decided the food style is
the player's choice and never a consequence of terminal size. With sprites the scale never drops
below 2, and `cap` sizing uses the whole grid cap instead of a smaller grid that fits, so the
terminal changes neither the food style nor the difficulty.

Invalid combinations are reported, never corrected. Sprites with a `cell_scale` below 2 are an
invalid configuration: `GameConfig` rejects them, the CLI reports a usage error before the TUI
starts, and the settings screen shows the reason and ignores ENTER until it is fixed, rather than
changing another setting to compensate. A terminal too small for the board at scale 2 is not a
configuration error: `SnakeView` draws a "terminal too small" message giving the size needed, and
`GameScreen.hold_for_size()` stops the game loop until there is room, then play continues.

## Considered options

- Fall back to glyph food at scale one (the previous behaviour): a setting the player chose could
  silently not apply.
- Shrink a capped grid until the board fits at scale 2: difficulty would depend on the terminal.

## Consequences

- Holding is not pausing: the model is untouched, and a pause taken while held still needs
  resuming afterwards.
- Only sprite food can make the terminal too small. Other boards are drawn at scale one at least,
  clipped if the terminal is below the supported 80×24.
- The built-in sprite modes use `fill` sizing, whose smallest grid fits at scale 2 in 80×24, so
  only a custom capped sprite board needs a bigger terminal.
