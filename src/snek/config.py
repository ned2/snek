"""Configuration settings and defaults for the Snek game."""

from dataclasses import dataclass
from typing import Final

from rich.cells import cell_len

from .worlds import WORLD_SPEEDS

# The smallest cell scale that can hold a food sprite: at scale 1 a cell is only
# 2x1 characters, far too small for pixel art.
MIN_SPRITE_SCALE: Final = 2

# How food is drawn: "diamond" is Nokia Snake's one fixed food; "glyphs" draws each
# world's themed Unicode symbols; "sprites" draws pixel art.
FOOD_TYPES: Final = ("diamond", "glyphs", "sprites")

# The "diamond" food's symbol.
DIAMOND: Final = "❖"

# How the world changes in a game: stay in the starting world, or move on.
WORLD_CHANGES: Final = ("fixed", "progress")

# The colour palettes: each world's own theme, or the Nokia LCD screen's.
PALETTES: Final = ("worlds", "lcd")


def _require_positive_int(name: str, value: object) -> int:
    """Return a positive integer or raise an actionable configuration error."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer, got {value!r}")
    if value < 1:
        raise ValueError(f"{name} must be at least 1, got {value}")
    return value


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
    # a ~280-col terminal at scale 3. Unused in "fill" mode. The defaults here and
    # below are the Classic mode's values (see `modes`): 20x11 is Nokia Snake's
    # board.
    max_grid_width: int = 20
    max_grid_height: int = 11

    # Cell magnification factor (k): each logical cell is drawn (2*k) x k glyphs.
    #   "cap" mode  — the *ceiling*; cells grow up to this as space allows.
    #   "fill" mode — the *exact* size; the grid fills the terminal at this scale.
    # With food sprites on it must be at least `MIN_SPRITE_SCALE`, and the board
    # never draws cells smaller than that (see `min_cell_scale`).
    cell_scale: int = 1

    # The world play starts in, from 1 to `len(WORLD_SPEEDS)`. A world sets the
    # speed (see `worlds.WORLD_SPEEDS`) and the points each food scores, like
    # Nokia Snake's level; it is the only source of speed.
    start_world: int = 5

    # How the world changes during a game, one of `WORLD_CHANGES`: "fixed" stays
    # in the starting world; "progress" moves on after every `foods_per_world`
    # foods, and stays in the last world once it gets there.
    world_change: str = "fixed"

    # Foods eaten before moving on to the next world (unused when fixed).
    foods_per_world: int = 50

    # The colours, one of `PALETTES`: "worlds" gives each world its own theme;
    # "lcd" is one two-tone green-grey theme, whatever the world.
    palette: str = "lcd"

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

    # How food is drawn, one of `FOOD_TYPES`. Sprites need cells of at least
    # `MIN_SPRITE_SCALE`, and the food style never changes with the terminal size:
    # a terminal too small for the board at that scale holds the game behind a
    # message rather than falling back to a glyph.
    food_type: str = "diamond"

    # The length the snake grows to at the start. It starts as one cell and
    # unrolls from there (see `Game.pending_growth`), so any length suits any board.
    start_length: int = 8

    # Interpolate movement between steps: the head slides into its new cell and
    # the tail drains out of the old one, instead of both jumping a whole cell.
    # Needs the default block/blank glyphs, and turns itself off at speeds where
    # a step lasts less than two frames.
    smooth_motion: bool = True

    # Solid board edges: moving off the board ends the game. Without them the
    # board wraps around, so the snake leaves one edge and enters the opposite.
    walls: bool = True

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

        if not isinstance(self.food_type, str) or self.food_type not in FOOD_TYPES:
            raise ValueError(
                f"food_type must be one of {', '.join(FOOD_TYPES)}, "
                f"got {self.food_type!r}"
            )

        _require_positive_int("cell_scale", self.cell_scale)
        _require_positive_int("start_length", self.start_length)
        _require_positive_int("foods_per_world", self.foods_per_world)
        _require_positive_int("max_buffered_turns", self.max_buffered_turns)
        _require_positive_int("side_panel_width", self.side_panel_width)

        world = _require_positive_int("start_world", self.start_world)
        if world > len(WORLD_SPEEDS):
            raise ValueError(
                f"start_world must be at most {len(WORLD_SPEEDS)}, got {world}"
            )
        for name, value, choices in (
            ("world_change", self.world_change, WORLD_CHANGES),
            ("palette", self.palette, PALETTES),
        ):
            if not isinstance(value, str) or value not in choices:
                raise ValueError(
                    f"{name} must be one of {', '.join(choices)}, got {value!r}"
                )

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

        for name, flag in (
            ("smooth_motion", self.smooth_motion),
            ("walls", self.walls),
        ):
            if not isinstance(flag, bool):
                raise ValueError(f"{name} must be a boolean, got {flag!r}")

        if self.cell_scale < self.min_cell_scale:
            raise ValueError(
                f"food sprites need a cell scale of at least {MIN_SPRITE_SCALE}, "
                f"got {self.cell_scale}"
            )

    @property
    def uses_sprites(self) -> bool:
        """Whether food is drawn as pixel-art sprites."""
        return self.food_type == "sprites"

    @property
    def min_cell_scale(self) -> int:
        """The smallest scale the board may be drawn at: sprites need room."""
        return MIN_SPRITE_SCALE if self.uses_sprites else 1


default_config: Final = GameConfig()
