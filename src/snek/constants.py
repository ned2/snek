"""Constants used throughout the Snek game."""


# Game states
class GameState:
    """Game state constants."""

    SPLASH = "splash"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"


# UI Constants
STATS_PANEL_WIDTH = 25
MIN_GAME_WIDTH = 10
MIN_GAME_HEIGHT = 10

# Key bindings
KEY_BINDINGS = {
    "up": ["up", "w", "k"],
    "down": ["down", "s", "j"],
    "left": ["left", "a", "h"],
    "right": ["right", "d", "l"],
    "pause": ["p"],
    "quit": ["q"],
    "restart": ["r"],
}
