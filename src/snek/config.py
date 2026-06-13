"""Configuration settings and defaults for the Snek game."""

from dataclasses import dataclass


@dataclass
class GameConfig:
    """Configuration settings for the Snake game."""

    # Grid dimensions
    default_grid_width: int = 20
    default_grid_height: int = 10

    # How the board is sized to the terminal. Two orthogonal strategies:
    #   "cap"  — fixed logical grid (clamped to `max_grid_*`); cells then grow up
    #            to `cell_scale` to fill the rest, leaving a framed letterbox.
    #            Difficulty is consistent across terminals; mid-size windows can
    #            sit below the next scale step (small board, wide margins).
    #   "fill" — fixed cell size (`cell_scale`); the logical grid grows to fill
    #            the whole terminal. No dead zone / margins, but difficulty and
    #            the length needed to win scale with the window size.
    sizing_mode: str = "cap"

    # Logical grid cap for "cap" mode (game cells = difficulty). The board grows
    # with the terminal up to this size, then stops. 36x20 (widescreen 9:5) fills
    # a ~280-col terminal at scale 3. Unused in "fill" mode.
    max_grid_width: int = 36
    max_grid_height: int = 20

    # Cell magnification factor (k): each logical cell is drawn (2*k) x k glyphs.
    #   "cap" mode  — the *ceiling*; cells grow up to this as space allows.
    #   "fill" mode — the *exact* size; the grid fills the terminal at this scale.
    # k >= 2 is required for food sprites (a k=1 cell is only 2x1 characters).
    cell_scale: int = 3

    # Speed settings
    initial_speed_interval: float = 0.1
    speed_increase_factor: float = 0.98

    # Hard floor on the tick interval — the fastest the snake may ever move.
    # Without it, `speed_increase_factor` compounds on every food with no bound,
    # and on a large board the demo AI eats enough food (~376) to drive the
    # interval down to ~50 us (~19,800 moves/sec). At that point the requested
    # tick rate is faster than the asyncio event loop can process one
    # `Game.step()` + board re-render, so the loop saturates (never sleeps, never
    # yields to input/repaint) and the app falls over mid-game.
    #
    # Crashing is the hard limit; watchability is the binding one. A big-board
    # step+render costs ~0.4 ms here, so 2 ms (500 moves/sec) still leaves the
    # loop ~5x headroom and stays well clear of the saturation wall on slower
    # machines. The practical ceiling is lower than the crash point, though:
    # past ~500 moves/sec the board updates faster than it can redraw cleanly and
    # the demo turns into hard-to-watch flicker. This is already well beyond what
    # a human can use — a later change may split this into separate human/demo
    # caps — but for now a single floor keeps every game both safe and watchable.
    min_speed_interval: float = 0.002

    # Symbols needed to advance to next world
    symbols_per_world: int = 10

    # How many queued turns may wait to be applied (one per tick). Buffering keeps
    # several keys pressed within a single tick from compounding into a reversal,
    # while still honouring a fast "up then left" as a two-step L-turn.
    max_buffered_turns: int = 2

    # UI settings
    side_panel_width: int = 30
    min_game_width: int = 10
    min_game_height: int = 10
    snake_block: str = "██"
    empty_cell: str = "  "

    # Draw food as pixel-art sprites when the cell is big enough (scale >=
    # sprites.MIN_SPRITE_SCALE); otherwise fall back to the themed glyph. Set
    # False to always use the glyph.
    food_sprites: bool = True


default_config = GameConfig()
