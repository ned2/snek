"""Game modes: named sets of every setting, designed to play well together.

A mode is nothing more than the values it gives the settings. Every mode gives
every setting on the settings screen (`MODE_FIELDS` and the demo strategy); a
setting that doesn't vary between modes simply has the same value in each.

The mode in force is derived from the settings, never stored: it is the first
mode whose values all match, else `CUSTOM`. Tweaking settings until they happen
to match a mode therefore shows that mode, and CLI flags map onto modes with no
extra state.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Final

from .config import GameConfig, default_config
from .demo import DEFAULT_STRATEGY


@dataclass(frozen=True)
class Settings:
    """Everything the settings screen edits: config values and the demo strategy.

    `values` override `base`, so settings being edited can hold a combination
    `GameConfig` would reject (e.g. sprites at cell scale 1) while the player is
    still stepping through rows. `to_config()` validates them; `error()` says why
    they are invalid, if they are.
    """

    base: GameConfig
    demo_strategy: str
    values: Mapping[str, object] = field(default_factory=dict[str, object])

    def get(self, name: str) -> object:
        """The value of config field `name`."""
        return self.values.get(name, getattr(self.base, name))

    def with_values(self, **changes: object) -> "Settings":
        """These settings with config fields changed; not validated."""
        return replace(self, values={**self.values, **changes})

    def to_config(self) -> GameConfig:
        """The validated config; raises ValueError if the values are invalid."""
        return replace(self.base, **self.values)

    def error(self) -> str | None:
        """Why the values are invalid, or None if they are valid."""
        try:
            self.to_config()
        except ValueError as error:
            return str(error)
        return None


@dataclass(frozen=True)
class Mode:
    """A named set of every setting's value, and a one-line description."""

    name: str
    description: str
    values: Mapping[str, object]
    demo_strategy: str = DEFAULT_STRATEGY

    @property
    def key(self) -> str:
        """The CLI spelling of the name, e.g. ``pixel-arena``."""
        return self.name.lower().replace(" ", "-")


# The config fields every mode gives: those on the settings screen.
MODE_FIELDS: Final = frozenset(
    {
        "walls",
        "initial_speed_interval",
        "start_length",
        "sizing_mode",
        "max_grid_width",
        "max_grid_height",
        "cell_scale",
        "smooth_motion",
        "food_type",
    }
)

# Shared by every mode: 10 moves a second, smooth motion, and a 36x20 grid cap
# (which fill sizing ignores).
_COMMON: Final = {
    "initial_speed_interval": 0.1,
    "smooth_motion": True,
    "max_grid_width": 36,
    "max_grid_height": 20,
}

# In display (and cycling) order. The first matches `GameConfig`'s defaults.
MODES: Final[tuple[Mode, ...]] = (
    Mode(
        "Classic",
        "Nokia-style: diamond food on a fixed 20x11 walled board.",
        {
            **_COMMON,
            "walls": True,
            "start_length": 8,
            "sizing_mode": "cap",
            "max_grid_width": 20,
            "max_grid_height": 11,
            "cell_scale": 1,
            "food_type": "diamond",
        },
    ),
    Mode(
        "Arcade",
        "Big pixel-art food on a walled board that fills the terminal.",
        {
            **_COMMON,
            "walls": True,
            "start_length": 3,
            "sizing_mode": "fill",
            "cell_scale": 4,
            "food_type": "sprites",
        },
    ),
    Mode(
        "Arena",
        "Glyph food on a wrapping board that fills the terminal.",
        {
            **_COMMON,
            "walls": False,
            "start_length": 3,
            "sizing_mode": "fill",
            "cell_scale": 1,
            "food_type": "glyphs",
        },
    ),
    Mode(
        "Pixel Arena",
        "Pixel-art food on a wrapping board that fills the terminal.",
        {
            **_COMMON,
            "walls": False,
            "start_length": 3,
            "sizing_mode": "fill",
            "cell_scale": 2,
            "food_type": "sprites",
        },
    ),
)

DEFAULT_MODE: Final = MODES[0]

# Shown when the settings match no mode. Never selectable: there is nothing to
# apply for it.
CUSTOM: Final = "Custom"
CUSTOM_DESCRIPTION: Final = "Your own mix of settings (S to change)."


def default_settings() -> Settings:
    """The settings a session starts with: the default mode's."""
    return Settings(base=default_config, demo_strategy=DEFAULT_STRATEGY)


def mode_named(name: str) -> Mode:
    """The mode called `name`."""
    return next(mode for mode in MODES if mode.name == name)


def mode_of(settings: Settings) -> str:
    """The name of the mode whose values `settings` has, or `CUSTOM`."""
    for mode in MODES:
        if settings.demo_strategy == mode.demo_strategy and all(
            settings.get(name) == value for name, value in mode.values.items()
        ):
            return mode.name
    return CUSTOM


def describe(name: str) -> str:
    """The one-line description of mode `name` (or of `CUSTOM`)."""
    return CUSTOM_DESCRIPTION if name == CUSTOM else mode_named(name).description


def apply_mode(settings: Settings, name: str) -> Settings:
    """`settings` with every value of mode `name`."""
    mode = mode_named(name)
    return replace(
        settings.with_values(**mode.values), demo_strategy=mode.demo_strategy
    )
