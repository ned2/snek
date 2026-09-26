"""The in-game settings: which options the settings screen offers and how they step.

Framework-free so the rules can be unit-tested without Textual. A `Settings`
value (see `modes`) holds config values and the demo-strategy name (which lives
on the app, not the config). Each `SettingRow` reads one option from it, offers
a fixed list of choices, and writes a chosen value back as a new `Settings`.
Writing does not validate: the settings screen steps freely through invalid
combinations, shows `Settings.error()`, and applies only valid settings.

Every setting applies from the next game: the screen is only reachable from the
splash, so nothing changes under a running game. Settings last for the session.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

from rich.cells import cell_len

from .config import FOOD_TYPES
from .demo import STRATEGIES
from .modes import CUSTOM, MODES, Settings, apply_mode, describe, mode_of


@dataclass(frozen=True)
class SettingRow:
    """One option on the settings screen.

    `choices` are in display order. Stepping past either end wraps round when
    `wrap` is set (for named options); ordered values such as speed stop at the
    ends instead. `show` formats a value for display. `help` is fixed text, or
    text worked out from the current settings.
    """

    label: str
    help: str | Callable[[Settings], str]
    choices: Sequence[Any]
    get: Callable[[Settings], Any]
    put: Callable[[Settings, Any], Settings]
    show: Callable[[Any], str] = str
    wrap: bool = False

    def value_text(self, settings: Settings) -> str:
        """The current value, formatted for display."""
        return self.show(self.get(settings))

    def help_text(self, settings: Settings) -> str:
        """The help line for this row, given the current settings."""
        return self.help if isinstance(self.help, str) else self.help(settings)

    def step(self, settings: Settings, delta: int) -> Settings:
        """Move `delta` choices along from the current value.

        A current value that is not one of the choices (e.g. an arbitrary
        `--speed`) steps to the nearest choice in that direction, and stays put
        if there is none. Named choices have no order, so from such a value (e.g.
        a "Custom" mode) they are entered at the first or last.
        """
        current = self.get(settings)
        choices = list(self.choices)
        if current in choices:
            index = choices.index(current) + delta
            if self.wrap:
                index %= len(choices)
            else:
                index = max(0, min(len(choices) - 1, index))
            return self.put(settings, choices[index])
        if self.wrap:
            return self.put(settings, choices[0 if delta > 0 else -1])
        if delta > 0:
            beyond = [choice for choice in choices if choice > current]
            return self.put(settings, beyond[0]) if beyond else settings
        below = [choice for choice in choices if choice < current]
        return self.put(settings, below[-1]) if below else settings


def _config(field: str) -> Callable[[Settings, Any], Settings]:
    """A `put` that sets one `GameConfig` field."""

    def put(settings: Settings, value: object) -> Settings:
        return settings.with_values(**{field: value})

    return put


def _on_off(value: bool) -> str:
    return "On" if value else "Off"


def _speed(settings: Settings) -> float:
    """The starting speed in moves per second, rounded so presets compare equal."""
    return round(1.0 / cast(float, settings.get("initial_speed_interval")), 6)


def _put_speed(settings: Settings, speed: float) -> Settings:
    return _config("initial_speed_interval")(settings, 1.0 / speed)


def _grid(settings: Settings) -> tuple[int, int]:
    width, height = settings.get("max_grid_width"), settings.get("max_grid_height")
    return cast(int, width), cast(int, height)


def _put_grid(settings: Settings, grid: tuple[int, int]) -> Settings:
    width, height = grid
    return settings.with_values(max_grid_width=width, max_grid_height=height)


SPEEDS = (2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50)
START_LENGTHS = tuple(range(1, 11))
GRIDS = ((20, 11), (24, 14), (36, 20), (48, 26), (60, 34))
SCALES = (1, 2, 3, 4, 5)

FOOD_HELP = {
    "diamond": "The classic Nokia diamond, in each world's colours.",
    "glyphs": "A new set of Unicode glyphs in each world.",
    "sprites": "Pixel-art food. Needs cell scale 2+.",
}

# The mode: one step applies a whole designed mix of the rows below it. The
# splash offers this row too.
MODE_ROW = SettingRow(
    label="Mode",
    help=lambda s: describe(mode_of(s)),
    choices=tuple(mode.name for mode in MODES),
    get=mode_of,
    put=apply_mode,
    wrap=True,
)

ROWS: tuple[SettingRow, ...] = (
    MODE_ROW,
    SettingRow(
        label="Walls",
        help="Solid edges end the game; off, the board wraps around.",
        choices=(False, True),
        get=lambda s: s.get("walls"),
        put=_config("walls"),
        show=_on_off,
        wrap=True,
    ),
    SettingRow(
        label="Starting speed",
        help="Moves per second at the start; the snake speeds up as it eats.",
        choices=SPEEDS,
        get=_speed,
        put=_put_speed,
        show=lambda v: f"{v:g} /sec",
    ),
    SettingRow(
        label="Starting length",
        help="Segments the snake unrolls to at the start.",
        choices=START_LENGTHS,
        get=lambda s: s.get("start_length"),
        put=_config("start_length"),
    ),
    SettingRow(
        label="Board sizing",
        help="Cap: a fixed grid, letterboxed. Fill: the grid fills the terminal.",
        choices=("cap", "fill"),
        get=lambda s: s.get("sizing_mode"),
        put=_config("sizing_mode"),
        show=lambda v: "Cap" if v == "cap" else "Fill",
        wrap=True,
    ),
    SettingRow(
        label="Grid cap",
        help="The largest grid in cap sizing, if the terminal fits it.",
        choices=GRIDS,
        get=_grid,
        put=_put_grid,
        show=lambda v: f"{v[0]} x {v[1]}",
    ),
    SettingRow(
        label="Cell scale",
        help="Characters per cell: the largest in cap sizing, exact in fill.",
        choices=SCALES,
        get=lambda s: s.get("cell_scale"),
        put=_config("cell_scale"),
    ),
    SettingRow(
        label="Smooth motion",
        help="Slide the snake between cells instead of jumping.",
        choices=(True, False),
        get=lambda s: s.get("smooth_motion"),
        put=_config("smooth_motion"),
        show=_on_off,
        wrap=True,
    ),
    SettingRow(
        label="Food type",
        help=lambda s: FOOD_HELP[cast(str, s.get("food_type"))],
        choices=FOOD_TYPES,
        get=lambda s: s.get("food_type"),
        put=_config("food_type"),
        show=str.capitalize,
        wrap=True,
    ),
    SettingRow(
        label="Demo strategy",
        help="Which algorithm plays the demo (D on the splash).",
        choices=tuple(sorted(STRATEGIES)),
        get=lambda s: s.demo_strategy,
        put=lambda s, v: replace(s, demo_strategy=v),
        wrap=True,
    ),
)


def widest_help(settings: Settings) -> int:
    """The width of the longest help line any row can show, in cells.

    Help worked out from the settings is counted for each of the row's choices,
    plus the Custom mode's description, which no choice selects.
    """
    texts = [describe(CUSTOM)]
    for row in ROWS:
        texts += [row.help_text(row.put(settings, choice)) for choice in row.choices]
    return max(cell_len(text) for text in texts)
