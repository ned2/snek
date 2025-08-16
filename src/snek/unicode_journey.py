"""World path management for food symbols in Snek."""
from dataclasses import dataclass
from typing import List, Dict
import random


@dataclass
class World:
    """A world in the journey with themed characters."""
    name: str
    description: str
    characters: List[str]
    

class WorldPath:
    """Manages the progression of food characters through worlds."""
    
    def __init__(self, levels_per_world: int = 2):
        """Initialize the world path.
        
        Args:
            levels_per_world: Number of levels before transitioning to next world
        """
        self.levels_per_world = levels_per_world
        self.worlds = self._create_journey_worlds()
        self._world_character_pool: Dict[int, List[str]] = {}
        
    def _create_journey_worlds(self) -> List[World]:
        """Create the journey through time and cultures."""
        return [
            World(
                name="Basic Symbols",
                description="Simple geometric shapes to begin our journey",
                characters=["●", "○", "■", "□", "▲", "▼", "◆", "◇", "★", "☆"]
            ),
            World(
                name="Ancient Egypt",
                description="Hieroglyphic symbols from the land of pharaohs",
                characters=["𓀀", "𓂀", "𓃀", "𓆣", "𓅱", "𓊖", "𓊗", "𓊘", "𓊙", "𓊚"]
            ),
            World(
                name="Classical Greece", 
                description="Letters and symbols from ancient Greek civilization",
                characters=["Α", "Β", "Γ", "Δ", "Θ", "Λ", "Ξ", "Π", "Σ", "Ω"]
            ),
            World(
                name="Norse Runes",
                description="Mystical runes from the Viking age",
                characters=["ᚠ", "ᚢ", "ᚦ", "ᚨ", "ᚱ", "ᚲ", "ᚷ", "ᚹ", "ᚺ", "ᚾ"]
            ),
            World(
                name="Alchemical Mysteries",
                description="Symbols from medieval alchemy and mysticism",
                characters=["🜁", "🜄", "🜍", "🜔", "🜛", "🜠", "🜨", "🜩", "🜪", "🜫"]
            ),
            World(
                name="Mathematical Realm",
                description="Logic and mathematical symbols",
                characters=["∴", "∵", "∞", "∇", "∂", "∫", "∑", "∏", "√", "∛"]
            ),
            World(
                name="Global Currencies",
                description="Currency symbols from around the world",
                characters=["₹", "₽", "₩", "₪", "₫", "₦", "₨", "₱", "₡", "₵"]
            ),
            World(
                name="Digital Age",
                description="Modern symbols and special characters",
                characters=["◉", "◈", "◊", "◌", "◍", "◎", "◐", "◑", "◒", "◓"]
            ),
        ]
    
    def get_world_for_level(self, level: int) -> World:
        """Get the world for a given level."""
        world_index = (level - 1) // self.levels_per_world
        world_index = world_index % len(self.worlds)  # Wrap around to start
        return self.worlds[world_index]
    
    def get_food_character(self, level: int) -> str:
        """Get a random food character for the current level.
        
        Ensures we don't repeat characters within a world until all are used.
        """
        world_index = (level - 1) // self.levels_per_world
        world_index = world_index % len(self.worlds)  # Wrap around to start
        
        # Initialize character pool for this world if needed
        if world_index not in self._world_character_pool:
            self._world_character_pool[world_index] = []
        
        # Refill pool if empty
        if not self._world_character_pool[world_index]:
            self._world_character_pool[world_index] = self.worlds[world_index].characters.copy()
            random.shuffle(self._world_character_pool[world_index])
        
        # Pop a character from the pool
        return self._world_character_pool[world_index].pop()
    
    def get_world_name(self, level: int) -> str:
        """Get the current world name for display."""
        return self.get_world_for_level(level).name
    
    def get_world_description(self, level: int) -> str:
        """Get the current world description."""
        return self.get_world_for_level(level).description
    
    def is_new_world(self, level: int) -> bool:
        """Check if this level starts a new world."""
        return (level - 1) % self.levels_per_world == 0 and level > 1
