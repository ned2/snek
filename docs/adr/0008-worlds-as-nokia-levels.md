# Worlds are Nokia Snake's levels, and the only source of speed

Decided 2026-09-26 (issue 0033); speed was redefined as pace on 2026-10-01 (issues 0036, 0037).

A **world** is one of nine stages of play, each with its own theme, food glyphs and pace. Worlds
began as a cosmetic journey through themes. In Nokia Snake the player picks a level from 1 to 9
before play: the level fixes the speed for the whole game and sets the points per food, and the game
gets harder only as the snake grows. Snek adopts that model as its worlds instead of adding levels
beside them: each world is a level, and the concept is called "World" everywhere (settings, CLI,
side panel and code), so there is one ladder of nine under one name. The world is the only source of
speed, with no speed-up per food and no separate speed setting. Play starts in the starting world
(chosen beside the mode, see [ADR 0007](0007-modes-derived-from-settings.md)). The **world change**
setting either keeps play there ("fixed", Nokia's rule) or moves on a world after every
`foods_per_world` foods ("progress"), staying in world 9 once there. Scoring is always on: each food
scores the number of the world it was eaten in, and filling the board adds `BOARD_CLEAR_BONUS`, both
Nokia's rules.

A world's **pace** (`WORLD_PACES`) is the snake's speed on screen, in rows per second, where a row
is the height of a scale-1 cell. It is not moves per second: at the same rate, bigger cells cover
more of the screen with each step and cross the board sooner, which plays much faster. So
`moves_per_second()` divides the pace by the cell scale, keeping the screen speed the same at every
scale, but never goes below a turn-lag floor. A key takes effect on the next step, so it can wait a
whole step, and at slow step rates that wait felt laggy in play. The floor rises gently with the
pace (`MIN_MOVES_PER_SECOND`, `FLOOR_PACE_EXPONENT`), so modes with big cells, which run on it,
still speed up from world to world. The scale used is the one the logical grid was established at
(`Game.cell_scale`, in either sizing mode, and 1 for a game no view has established), so a resize
never changes the speed. Nokia's own timings are unknown, so the pace ladder is Snek's own,
calibrated in play.

## Considered options

- **A speed-up on every food** (Snek's original behaviour, with a starting-speed setting): Nokia has
  none, and speed would then come from two places, so a world could not stand for a level.
- **A separate level setting beside the worlds**: two overlapping progressions under two names.
- **A ladder of moves per second** (until 2026-10-01): the slowest rate that was playable with
  Arcade's big cells was painfully slow on Arena's scale-1 board, so no one ladder suited every
  mode.
- **Dividing by a fractional power of the scale** (tried at ⅓ and 0.37): measured in the real app,
  Arcade crossed the screen in about half the time the other modes took, while Classic and Arena,
  which share a screen speed, both felt right. Equal screen speed fitted play better.
- **A flat turn-lag floor**: big cells sat on it in almost every world, so Arcade barely sped up.
- **Hiding the turn lag in the drawing** (hurrying the turning step, drawing ahead of the model,
  rushing the drawn head to the corner): each read in play as a jump, a stutter or a change of pace.
  [ADR 0006](0006-interpolated-motion.md) covers how motion is drawn.

## Consequences

- Big cells that run on the floor move faster on screen than their pace, and speed up less from
  world to world than scale-1 cells do.
- In cap sizing the established scale depends on the terminal, so the same world can run at a
  different number of moves per second on another terminal, at the same screen speed.
- The side panel shows the pace, not moves per second; diagnostics show both, and the established
  scale.
- The top pace at scale 1 must stay below the step rate at which a step lasts under two frames,
  where smooth motion stops interpolating.
