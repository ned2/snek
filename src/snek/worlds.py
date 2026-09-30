"""World path management for food symbols in Snek.

A world is a Nokia Snake level: its number sets the pace (`WORLD_PACES`) and
the points each food scores, and it also has a theme and a set of food glyphs.
"""

import math
import random
from dataclasses import dataclass
from typing import Final

from textual.theme import Theme

from .themes import THEME_MAP

# The pace of each world, from world 1 to world 9, evenly spaced (a constant
# ratio, about 1.12x per world) from 10 to 25. Pace is how fast the snake moves
# on screen: rows per second, where a row is the height of a scale-1 cell. At
# scale 1 it is the moves per second; bigger cells move fewer cells a second at
# the same pace, down to a floor (see `moves_per_second`). Our own calibration;
# Nokia's timings are unknown. World 9 at scale 1 stays under the 30 moves a
# second above which a step spans under two frames and smooth motion stops
# interpolating.
WORLD_PACES: Final = tuple(round(10 * 2.5 ** (k / 8), 1) for k in range(9))

# The fewest moves per second, in world 1. Below 7.5 a turn waits noticeably
# long for the next step: 6.6 still lagged slightly in play and 7.4 felt good
# (issues 0036, 0037).
MIN_MOVES_PER_SECOND: Final = 7.5

# How fast that floor rises with the pace: `MIN_MOVES_PER_SECOND` times
# `(pace / WORLD_PACES[0]) ** FLOOR_PACE_EXPONENT`. Big cells sit on the floor,
# so without the rise they would barely speed up from world to world. 0.37
# takes it from 7.5 to about 10.5 moves a second across the worlds (issue 0037).
FLOOR_PACE_EXPONENT: Final = 0.37


def moves_per_second(pace: float, scale: int) -> float:
    """The moves per second that give `pace` with cells drawn at `scale`.

    A step at a bigger scale covers more of the screen, so the same moves per
    second looks and feels faster. Dividing by the scale keeps the screen speed
    the same (what play found speed feels like), down to a floor that rises
    gently with the pace: below it the turn lag wins, so big cells move faster
    on screen than the pace.
    """
    floor = MIN_MOVES_PER_SECOND * math.pow(pace / WORLD_PACES[0], FLOOR_PACE_EXPONENT)
    return max(pace / scale, floor)


@dataclass
class World:
    """A world in the journey with themed characters."""

    name: str
    description: str
    characters: list[str]
    theme_name: str

    @property
    def theme(self) -> Theme:
        """Get the theme object for this world."""
        return THEME_MAP[self.theme_name]


class WorldPath:
    """Manages the progression of food characters through worlds."""

    def __init__(self, rng: random.Random | None = None) -> None:
        """Initialize the world path."""
        self._rng = rng or random.Random()
        self.worlds = self._create_journey_worlds()
        self._world_character_pool: dict[int, list[str]] = {}

    def _create_journey_worlds(self) -> list[World]:
        """Create the journey through time and cultures."""
        return [
            World(
                name="Basic Symbols",
                description="Simple geometric shapes to begin our journey",
                characters=["●", "○", "■", "□", "▲", "▼", "◆", "◇", "★", "☆"],
                theme_name="snek-classic",
            ),
            World(
                name="Ancient Egypt",
                description="Hieroglyphic symbols from the land of pharaohs",
                characters=["𓀀", "𓂀", "𓃀", "𓆣", "𓅱", "𓊖", "𓊗", "𓊘", "𓊙", "𓊚"],
                theme_name="snek-ocean",
            ),
            World(
                name="Classical Greece",
                description="Letters and symbols from ancient Greek civilization",
                characters=["Α", "Β", "Γ", "Δ", "Θ", "Λ", "Ξ", "Π", "Σ", "Ω"],
                theme_name="snek-sunset",
            ),
            World(
                name="Norse Runes",
                description="Mystical runes from the Viking age",
                characters=["ᚠ", "ᚢ", "ᚦ", "ᚨ", "ᚱ", "ᚲ", "ᚷ", "ᚹ", "ᚺ", "ᚾ"],
                theme_name="snek-royal",
            ),
            World(
                name="Alchemical Mysteries",
                description="Symbols from medieval alchemy and mysticism",
                characters=["🜁", "🜄", "🜍", "🜔", "🜛", "🜠", "🜨", "🜩", "🜪", "🜫"],
                theme_name="snek-cherry",
            ),
            World(
                name="Mathematical Realm",
                description="Logic and mathematical symbols",
                characters=["∴", "∵", "∞", "∇", "∂", "∫", "∑", "∏", "√", "∛"],
                theme_name="snek-classic",
            ),
            World(
                name="Global Currencies",
                description="Currency symbols from around the world",
                characters=["₹", "₽", "₩", "₪", "₫", "₦", "₨", "₱", "₡", "₵"],
                theme_name="snek-ocean",
            ),
            World(
                name="Digital Age",
                description="Modern symbols and special characters",
                characters=["◉", "◈", "◊", "◌", "◍", "◎", "◐", "◑", "◒", "◓"],
                theme_name="snek-sunset",
            ),
            World(
                name="Celestial",
                description="The sun, the moon and the planets",
                characters=["☉", "☽", "☿", "♀", "♂", "♃", "♄", "♅", "♆", "♇"],
                theme_name="snek-royal",
            ),
        ]

    def get_world(self, world_index: int) -> World:
        """Get the world by index (from 0); there is no world after the last."""
        return self.worlds[world_index]

    def get_food_character(self, world_index: int) -> str:
        """Get a random food character for the current world.

        Ensures we don't repeat characters within a world until all are used.
        """
        # Initialize character pool for this world if needed
        if world_index not in self._world_character_pool:
            self._world_character_pool[world_index] = []

        # Refill pool if empty
        if not self._world_character_pool[world_index]:
            self._world_character_pool[world_index] = self.worlds[
                world_index
            ].characters.copy()
            self._rng.shuffle(self._world_character_pool[world_index])

        # Pop a character from the pool
        return self._world_character_pool[world_index].pop()

    def get_world_name(self, world_index: int) -> str:
        """Get the world name for display."""
        return self.get_world(world_index).name

    def get_world_description(self, world_index: int) -> str:
        """Get the world description."""
        return self.get_world(world_index).description
