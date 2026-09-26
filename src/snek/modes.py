"""Game modes: named sets of board settings designed to play well together.

A mode is nothing more than the values it gives the settings it owns. The mode in
force is derived from the config, never stored: it is the first mode whose values
all match, else `CUSTOM`. Tweaking settings until they happen to match a mode
therefore shows that mode, and CLI flags map onto modes with no extra state.

Modes own the board's look, size and edges. Speed, smooth motion and the demo
strategy are left alone, so changing them never makes a mode "Custom".
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from .config import GameConfig


@dataclass(frozen=True)
class Mode:
    """A named set of config values, and a one-line description for players."""

    name: str
    description: str
    values: Mapping[str, object]

    @property
    def key(self) -> str:
        """The CLI spelling of the name, e.g. ``pixel-arena``."""
        return self.name.lower().replace(" ", "-")


# In display (and cycling) order. The first matches `GameConfig`'s defaults. Fill
# modes leave the grid cap alone, since fill sizing never reads it.
MODES: Final[tuple[Mode, ...]] = (
    Mode(
        "Classic",
        "Glyph food on a fixed 36x20 walled board.",
        {
            "walls": True,
            "sizing_mode": "cap",
            "max_grid_width": 36,
            "max_grid_height": 20,
            "cell_scale": 1,
            "food_sprites": False,
        },
    ),
    Mode(
        "Arcade",
        "Big pixel-art food on a walled board that fills the terminal.",
        {
            "walls": True,
            "sizing_mode": "fill",
            "cell_scale": 4,
            "food_sprites": True,
        },
    ),
    Mode(
        "Arena",
        "Glyph food on a wrapping board that fills the terminal.",
        {
            "walls": False,
            "sizing_mode": "fill",
            "cell_scale": 1,
            "food_sprites": False,
        },
    ),
    Mode(
        "Pixel Arena",
        "Pixel-art food on a wrapping board that fills the terminal.",
        {
            "walls": False,
            "sizing_mode": "fill",
            "cell_scale": 2,
            "food_sprites": True,
        },
    ),
)

DEFAULT_MODE: Final = MODES[0]

# Shown when the config matches no mode. Never selectable: there is nothing to
# apply for it.
CUSTOM: Final = "Custom"
CUSTOM_DESCRIPTION: Final = "Your own mix of settings (S to change)."


def mode_named(name: str) -> Mode:
    """The mode called `name`."""
    return next(mode for mode in MODES if mode.name == name)


def mode_of(config: GameConfig) -> str:
    """The name of the mode whose values `config` has, or `CUSTOM`."""
    for mode in MODES:
        if all(getattr(config, field) == value for field, value in mode.values.items()):
            return mode.name
    return CUSTOM


def describe(name: str) -> str:
    """The one-line description of mode `name` (or of `CUSTOM`)."""
    return CUSTOM_DESCRIPTION if name == CUSTOM else mode_named(name).description


def apply_mode(config: GameConfig, name: str) -> GameConfig:
    """`config` with every value of mode `name`, applied (and validated) at once."""
    return replace(config, **mode_named(name).values)
