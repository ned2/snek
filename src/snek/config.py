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

    # Hard floor on the tick interval — the fastest the snake may ever move.
    # Without it, `speed_increase_factor` compounds on every food with no bound,
    # and on a large board the demo AI eats enough food (~376) to drive the
    # interval down to ~50 us (~19,800 moves/sec). At that point the requested
    # tick rate is faster than the asyncio event loop can process one
    # `Game.step()` + board re-render, so the loop saturates (never sleeps, never
    # yields to input/repaint) and the app falls over mid-game.
    #
    # A big-board step+render costs ~0.4 ms here; 4 ms (250 moves/sec) leaves the
    # loop ~10x headroom, so it stays healthy even on machines several times
    # slower or with coarser timer resolution. This is well above what a human
    # can use — a later change may split this into separate human/demo caps — but
    # for now a single floor keeps every game safe across machines.
    min_speed_interval: float = 0.004

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


default_config = GameConfig()
