"""The in-game settings: which options the settings screen offers and how they step.

Framework-free so the rules can be unit-tested without Textual. A `Settings`
value pairs the immutable `GameConfig` with the demo-strategy name (which lives
on the app, not the config). Each `SettingRow` reads one option from it, offers
a fixed list of choices, and writes a chosen value back as a new `Settings` —
through `dataclasses.replace`, so `GameConfig` still validates every change.

Every setting applies from the next game: the screen is only reachable from the
splash, so nothing changes under a running game. Settings last for the session.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from rich.cells import cell_len

from .config import GameConfig
from .demo import STRATEGIES
from .modes import CUSTOM, MODES, apply_mode, describe, mode_of


@dataclass(frozen=True)
class Settings:
    """Everything the settings screen edits."""

    config: GameConfig
    demo_strategy: str


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
        return replace(settings, config=replace(settings.config, **{field: value}))

    return put


def _on_off(value: bool) -> str:
    return "On" if value else "Off"


def _speed(settings: Settings) -> float:
    """The starting speed in moves per second, rounded so presets compare equal."""
    return round(1.0 / settings.config.initial_speed_interval, 6)


def _put_speed(settings: Settings, speed: float) -> Settings:
    return _config("initial_speed_interval")(settings, 1.0 / speed)


def _grid(settings: Settings) -> tuple[int, int]:
    return (settings.config.max_grid_width, settings.config.max_grid_height)


def _put_grid(settings: Settings, grid: tuple[int, int]) -> Settings:
    width, height = grid
    config = replace(settings.config, max_grid_width=width, max_grid_height=height)
    return replace(settings, config=config)


SPEEDS = (2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50)
GRIDS = ((16, 10), (24, 14), (36, 20), (48, 26), (60, 34))
SCALES = (1, 2, 3, 4, 5)

# The mode: one step applies a whole designed mix of the rows below it. The
# splash offers this row too.
MODE_ROW = SettingRow(
    label="Mode",
    help=lambda s: describe(mode_of(s.config)),
    choices=tuple(mode.name for mode in MODES),
    get=lambda s: mode_of(s.config),
    put=lambda s, name: replace(s, config=apply_mode(s.config, name)),
    wrap=True,
)

ROWS: tuple[SettingRow, ...] = (
    MODE_ROW,
    SettingRow(
        label="Walls",
        help="Solid edges end the game; off, the board wraps around.",
        choices=(False, True),
        get=lambda s: s.config.walls,
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
        label="Board sizing",
        help="Cap: a fixed grid, letterboxed. Fill: the grid fills the terminal.",
        choices=("cap", "fill"),
        get=lambda s: s.config.sizing_mode,
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
        get=lambda s: s.config.cell_scale,
        put=_config("cell_scale"),
    ),
    SettingRow(
        label="Smooth motion",
        help="Slide the snake between cells instead of jumping.",
        choices=(True, False),
        get=lambda s: s.config.smooth_motion,
        put=_config("smooth_motion"),
        show=_on_off,
        wrap=True,
    ),
    SettingRow(
        label="Food sprites",
        help="Pixel-art food. Needs cell scale 2+ and a terminal to fit it.",
        choices=(True, False),
        get=lambda s: s.config.food_sprites,
        put=_config("food_sprites"),
        show=_on_off,
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


def widest_help() -> int:
    """The width of the longest help line any row can show, in cells.

    Fixed help is counted as is; the Mode row's help is a mode description.
    """
    texts = [row.help for row in ROWS if isinstance(row.help, str)]
    texts += [describe(mode.name) for mode in MODES] + [describe(CUSTOM)]
    return max(cell_len(text) for text in texts)
