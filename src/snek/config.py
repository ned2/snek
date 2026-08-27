"""Configuration settings and defaults for the Snek game."""

from dataclasses import dataclass
import math
from typing import Final

from rich.cells import cell_len


def _require_positive_int(name: str, value: object) -> int:
    """Return a positive integer or raise an actionable configuration error."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer, got {value!r}")
    if value < 1:
        raise ValueError(f"{name} must be at least 1, got {value}")
    return value


def _require_positive_finite(name: str, value: object) -> float:
    """Return a finite positive number or raise an actionable error."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be a number, got {value!r}")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be finite and greater than 0, got {value!r}")
    return number


def validate_dimensions(width: object, height: object) -> None:
    """Validate supported model dimensions.

    One-cell-wide or one-cell-high boards are valid, but a 1x1 board cannot
    contain both the initial snake and food and is rejected before construction.
    """
    valid_width = _require_positive_int("width", width)
    valid_height = _require_positive_int("height", height)
    if valid_width * valid_height < 2:
        raise ValueError(
            f"board must contain at least 2 cells, got {valid_width}x{valid_height}"
        )


@dataclass(frozen=True)
class GameConfig:
    """Immutable configuration value for the Snake game.

    Instances may be shared safely. Use `dataclasses.replace` to derive a
    validated configuration with overrides rather than mutating an instance.
    """

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

    def __post_init__(self) -> None:
        """Reject invalid configuration at its construction boundary."""
        if not isinstance(self.sizing_mode, str) or self.sizing_mode not in {
            "cap",
            "fill",
        }:
            raise ValueError(
                f"sizing_mode must be 'cap' or 'fill', got {self.sizing_mode!r}"
            )

        dimensions = {
            name: _require_positive_int(name, value)
            for name, value in (
                ("default_grid_width", self.default_grid_width),
                ("default_grid_height", self.default_grid_height),
                ("min_game_width", self.min_game_width),
                ("min_game_height", self.min_game_height),
                ("max_grid_width", self.max_grid_width),
                ("max_grid_height", self.max_grid_height),
            )
        }
        for label, width_name, height_name in (
            ("default grid", "default_grid_width", "default_grid_height"),
            ("minimum game grid", "min_game_width", "min_game_height"),
            ("maximum game grid", "max_grid_width", "max_grid_height"),
        ):
            if dimensions[width_name] * dimensions[height_name] < 2:
                raise ValueError(f"{label} must contain at least 2 cells")
        if dimensions["max_grid_width"] < dimensions["min_game_width"]:
            raise ValueError(
                "max_grid_width must be greater than or equal to min_game_width"
            )
        if dimensions["max_grid_height"] < dimensions["min_game_height"]:
            raise ValueError(
                "max_grid_height must be greater than or equal to min_game_height"
            )

        _require_positive_int("cell_scale", self.cell_scale)
        _require_positive_int("symbols_per_world", self.symbols_per_world)
        _require_positive_int("max_buffered_turns", self.max_buffered_turns)
        _require_positive_int("side_panel_width", self.side_panel_width)

        initial_interval = _require_positive_finite(
            "initial_speed_interval", self.initial_speed_interval
        )
        minimum_interval = _require_positive_finite(
            "min_speed_interval", self.min_speed_interval
        )
        if initial_interval < minimum_interval:
            raise ValueError(
                "initial_speed_interval must be greater than or equal to "
                "min_speed_interval"
            )
        speed_factor = _require_positive_finite(
            "speed_increase_factor", self.speed_increase_factor
        )
        if speed_factor > 1:
            raise ValueError("speed_increase_factor must be less than or equal to 1")

        for name, glyph in (
            ("snake_block", self.snake_block),
            ("empty_cell", self.empty_cell),
        ):
            if not isinstance(glyph, str):
                raise ValueError(f"{name} must be a string, got {glyph!r}")
            width = cell_len(glyph)
            if width != 2:
                raise ValueError(
                    f"{name} must occupy exactly 2 terminal cells, got {width}"
                )

        if not isinstance(self.food_sprites, bool):
            raise ValueError(
                f"food_sprites must be a boolean, got {self.food_sprites!r}"
            )


default_config: Final = GameConfig()
