"""Configuration settings and defaults for the Snek game."""

from dataclasses import dataclass


@dataclass
class GameConfig:
    """Configuration settings for the Snake game."""

    # Grid dimensions
    default_grid_width: int = 20
    default_grid_height: int = 10

    # Hard cap on the *logical* grid (game cells, which set difficulty and the
    # length needed to fill the board). The board no longer grows to fill the
    # terminal; instead the logical grid is clamped to this size and the renderer
    # scales each cell up visually (see `max_cell_scale`). 20x15 fits at scale 1
    # in an 80x24 terminal (minus the side panel), so essentially every terminal
    # gets the same board — difficulty stops depending on window size.
    max_grid_width: int = 20
    max_grid_height: int = 15

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

    # Largest integer factor the renderer may scale a cell by to fill the
    # terminal. Each logical cell is drawn as a (2*k) x k block of glyphs, so the
    # board uses available space without enlarging the logical grid. Capped so
    # cells never get grotesquely chunky on very large terminals; small terminals
    # are forced to k=1 regardless.
    max_cell_scale: int = 3


default_config = GameConfig()
