"""Constants used throughout the Snek game."""


class GameState:
    """Game state constants."""

    SPLASH = "splash"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"


STATS_PANEL_WIDTH = 25
MIN_GAME_WIDTH = 10
MIN_GAME_HEIGHT = 10

KEY_BINDINGS = {
    "up": ["up", "w", "k"],
    "down": ["down", "s", "j"],
    "left": ["left", "a", "h"],
    "right": ["right", "d", "l"],
    "pause": ["p"],
    "quit": ["q"],
    "restart": ["r"],
}
