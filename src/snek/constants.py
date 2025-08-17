"""Constants used throughout the Snek game."""


class GameState:
    """Game state constants."""

    SPLASH = "splash"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"


SIDE_PANEL_WIDTH = 25
MIN_GAME_WIDTH = 10
MIN_GAME_HEIGHT = 10

KEY_BINDINGS = {
    "up": ["up", "w"],
    "down": ["down", "s"],
    "left": ["left", "a"],
    "right": ["right", "d"],
    "pause": ["p"],
    "quit": ["q"],
    "start": ["enter"],
    "continue": ["enter"],
    "restart": ["enter"],
}
