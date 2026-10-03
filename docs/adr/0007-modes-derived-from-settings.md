# Modes are derived from the settings, which are edited as a validated draft

Decided 2026-09-26 (issues 0029, 0030, 0031); the starting world was taken out of the modes on
2026-10-01 (issue 0038).

Several settings only make sense together: food sprites need a cell scale of at least 2, glyph food
gains nothing from a scale above 1, and the cell scale is a ceiling on a capped board but exact on
one that fills the terminal. No single set of defaults suits them all. So a **mode** (Classic,
Arcade, Arena, Pixel Arena) is a named collection of setting values that play well together, and
nothing more. The mode in force is never stored: `mode_of()` derives it from the current `Settings`
as the first mode in `MODES` whose values all match, else **Custom**, the name shown for settings
that match no mode. Invalid settings are always Custom, since no mode is invalid. Tweaking settings
until they land on a mode's values therefore shows that mode, and CLI flags (`--mode`, then any
single-setting overrides) map onto a mode with no extra state. Custom is shown but never selectable:
there is nothing to apply for it.

Modes are exhaustive: each gives every settings-screen field (`MODE_FIELDS`) and the demo strategy.
Applying one (`apply_mode()`, a single replacement that never passes through an invalid combination)
resets them all, so a mode's name tells you the whole game being played. The one exception is the
starting **world** (see [ADR 0008](0008-worlds-as-nokia-levels.md)), which stands for Nokia Snake's
level, a choice its player makes before every game. The player picks the world beside the mode, on
the splash and in the settings row after Mode. No mode sets it or matches on it, and it survives
mode changes.

Settings last for the session only and are reachable only from the splash, so nothing changes under
a running game and every setting applies from the next one. The settings screen edits a draft
(`Settings`: raw values over a base `GameConfig`). Any row can step to any of its values, including
combinations `GameConfig` rejects, such as sprites at cell scale 1. After every change the draft is
validated by building a `GameConfig`, the same check that makes a bad combination of flags a CLI
usage error, and the reason it fails, if any, is shown. ENTER applies the draft only when it is
valid; ESC discards it.

## Considered options

- **Modes that set only the board fields** (the first version): speed, smoothing and the demo
  strategy carried over from whatever was set before, so a mode's name didn't say how the game
  would play. Exhaustive modes accept that changing any of those makes the mode Custom.
- **A stored mode, or a remembered Custom**: extra state that could disagree with the settings it
  names.
- **Refusing a step that would make the settings invalid**: some valid combinations could then be
  reached only by changing rows in a particular order.
- **Keeping the starting world in the modes**: choosing world 4 in Classic made it Custom, and
  stepping the mode reset the world to 1. Modes that set a world without matching on it would still
  reset it on every mode step, and a mode per world would multiply the modes by nine.

## Consequences

- A new settings-screen field needs a value in every mode and a place in `MODE_FIELDS`, unless it
  is a deliberate exception like the starting world; `tests/test_modes.py` checks this. Config
  fields that aren't on the settings screen, such as `max_buffered_turns`, stay outside modes.
- No setting can change mid-game, not even a visual one such as smooth motion.
