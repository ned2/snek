"""Pure helpers for sizing and drawing the board.

These are deliberately framework-free (no Textual, no widget state) so the
layout maths and the scaled-board string can be unit-tested directly. The board
decouples two quantities:

- the *logical grid* (`compute_grid_size`): how many game cells there are, which
  fixes difficulty and how much the snake must eat to fill the board, and
- the *visual scale* (`compute_scale`): how many terminal characters draw one
  cell, which only affects how much of the terminal the board covers.

`render_board` turns a game state plus a scale factor into the text the
`SnakeView` displays.
"""

from .config import GameConfig
from .game_rules import Position

# A logical cell is drawn `CELL_BASE_WIDTH` columns wide by one row tall at
# scale 1. Terminal character cells are roughly twice as tall as wide, so two
# columns per cell makes a cell look square — the same trick the snake/empty
# glyphs ("██" / "  ") already rely on.
CELL_BASE_WIDTH = 2


def compute_grid_size(
    avail_cols: int, avail_rows: int, config: GameConfig
) -> tuple[int, int]:
    """Pick the logical grid (in cells) for the space the board may use.

    Clamped to ``[min_game_*, max_grid_*]`` using the scale-1 footprint (each
    cell is `CELL_BASE_WIDTH` columns wide). Any terminal large enough lands on
    the cap exactly, so the board is identical everywhere; only windows too small
    for the cap shrink it.
    """
    width = max(
        config.min_game_width,
        min(config.max_grid_width, avail_cols // CELL_BASE_WIDTH),
    )
    height = max(
        config.min_game_height,
        min(config.max_grid_height, avail_rows),
    )
    return width, height


def compute_scale(
    avail_cols: int,
    avail_rows: int,
    grid_width: int,
    grid_height: int,
    config: GameConfig,
) -> int:
    """Largest integer cell scale that fits the grid in the space, capped.

    A cell occupies ``CELL_BASE_WIDTH * k`` columns and ``k`` rows, so we take
    the largest ``k`` that fits both axes, floor it at 1 (the board may overflow
    a tiny terminal rather than vanish) and cap it at ``max_cell_scale``.
    """
    fit_cols = avail_cols // (CELL_BASE_WIDTH * grid_width)
    fit_rows = avail_rows // grid_height
    return max(1, min(fit_cols, fit_rows, config.max_cell_scale))


def render_board(
    width: int,
    height: int,
    snake: set[Position],
    food: Position,
    food_symbol: str,
    snake_block: str,
    empty_cell: str,
    scale: int,
) -> str:
    """Draw the board as text, each logical cell a ``(2*scale) x scale`` block.

    Snake and empty cells tile their base glyph (`snake_block` / `empty_cell`,
    each `CELL_BASE_WIDTH` columns) `scale` times across and down. The food glyph
    is centred in its block — placed on the block's middle row, padded to the
    block width — matching the single-width-glyph assumption the unscaled
    renderer already made.
    """
    block_width = CELL_BASE_WIDTH * scale
    mid_row = scale // 2
    empty_row = empty_cell * scale

    # Pre-build the `scale` rows for a food cell once; the glyph never moves.
    food_rows = [
        (food_symbol + " ").center(block_width) if r == mid_row else empty_row
        for r in range(scale)
    ]

    lines: list[str] = []
    for y in range(height):
        block_rows = ["" for _ in range(scale)]
        for x in range(width):
            pos = (x, y)
            if pos in snake:
                for r in range(scale):
                    block_rows[r] += snake_block * scale
            elif pos == food:
                for r in range(scale):
                    block_rows[r] += food_rows[r]
            else:
                for r in range(scale):
                    block_rows[r] += empty_row
        lines.extend(block_rows)
    return "\n".join(lines)
