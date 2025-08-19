"""Configuration settings and defaults for the Snek game."""

from dataclasses import dataclass


@dataclass
class GameConfig:
    """Configuration settings for the Snake game."""

    # Grid dimensions
    default_grid_width: int = 20
    default_grid_height: int = 10

    # Speed settings
    initial_speed_interval: float = 0.1
    speed_increase_factor: float = 0.98

    # Symbols needed to advance to next world
    symbols_per_world: int = 10

    # UI settings
    side_panel_width: int = 30
    min_game_width: int = 10
    min_game_height: int = 10
    snake_block: str = "██"
    empty_cell: str = "  "


default_config = GameConfig()
