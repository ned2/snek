"""World path management for food symbols in Snek."""

from dataclasses import dataclass
import random

from .themes import THEME_MAP


@dataclass
class World:
    """A world in the journey with themed characters."""

    name: str
    description: str
    characters: list[str]
    theme_name: str

    @property
    def theme(self):
        """Get the theme object for this world."""
        return THEME_MAP[self.theme_name]


class WorldPath:
    """Manages the progression of food characters through worlds."""

    def __init__(self):
        """Initialize the world path."""
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
        ]

    def get_world(self, world_index: int) -> World:
        """Get the world by index, wrapping to start if all completed."""
        return self.worlds[world_index % len(self.worlds)]

    def get_food_character(self, world_index: int) -> str:
        """Get a random food character for the current world.

        Ensures we don't repeat characters within a world until all are used.
        """
        world_index = world_index % len(self.worlds)

        # Initialize character pool for this world if needed
        if world_index not in self._world_character_pool:
            self._world_character_pool[world_index] = []

        # Refill pool if empty
        if not self._world_character_pool[world_index]:
            self._world_character_pool[world_index] = self.worlds[
                world_index
            ].characters.copy()
            random.shuffle(self._world_character_pool[world_index])

        # Pop a character from the pool
        return self._world_character_pool[world_index].pop()

    def get_world_name(self, world_index: int) -> str:
        """Get the world name for display."""
        return self.get_world(world_index).name

    def get_world_description(self, world_index: int) -> str:
        """Get the world description."""
        return self.get_world(world_index).description
