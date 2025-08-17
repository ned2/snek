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

    # Game progression
    symbols_per_level: int = 5

    # UI settings
    stats_panel_width: int = 25
    snake_block: str = "██"
    empty_cell: str = "  "

    # Colors
    default_color: str = "green"
    level_colors: list[str] = None

    # Food symbols
    food_symbols: list[str] = None

    # Number of levels before changing character class
    levels_per_unicode_phase: int = 2

    def __post_init__(self):
        """Initialize mutable defaults."""
        if self.level_colors is None:
            self.level_colors = [
                "green",
                "blue",
                "cyan",
                "magenta",
                "yellow",
                "red",
                "white",
            ]

        if self.food_symbols is None:
            self.food_symbols = ["*", "@", "#", "$", "%", "&", "§", "¤", "¶", "☼", "☻"]


default_config = GameConfig()
