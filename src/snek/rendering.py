"""Pure helpers for sizing and drawing the board.

These are deliberately framework-free (no Textual widgets, no widget state) so the
layout maths and the board contents can be unit-tested directly. The board
decouples two quantities — the *logical grid* (game cells, which fix difficulty)
and the *visual scale* (characters per cell). `compute_layout` resolves both for
a fresh game's initial viewport according to the sizing mode:

- "cap": fix the grid (clamped to `max_grid_*`), then take the largest scale that
  fits up to `cell_scale` — a consistent, bounded board that may be letterboxed.
- "fill": fix the scale at `cell_scale`, then grow the grid to fill the space —
  fills the terminal, but the grid (and difficulty) vary with the window.

Once play begins the logical grid is fixed. `fit_grid_scale` changes only the
visual scale as the viewport changes, so a terminal resize can never rewrite
snake or food coordinates.

`render_board` turns a game state into Rich `Segment`s (so individual cells can
carry their own colour — e.g. a food sprite). The food cell is supplied as a
pre-built *tile* so the board walker stays independent of how food is drawn:
`glyph_food_tile` keeps the single themed glyph; a sprite tile (see `sprites`)
swaps in pixel art. Both are `scale` rows tall and `2*scale` columns wide.
"""

from rich.segment import Segment
from rich.style import Style

from .config import GameConfig
from .game_rules import Position

# Subtle frame around the play area; dim so it reads as chrome, not as snake.
# No explicit colour, so it inherits the widget's colour (theme primary).
_BORDER_STYLE = Style(dim=True)

# A logical cell is drawn `CELL_BASE_WIDTH` columns wide by one row tall at
# scale 1. Terminal character cells are roughly twice as tall as wide, so two
# columns per cell makes a cell look square — the same trick the snake/empty
# glyphs ("██" / "  ") already rely on.
CELL_BASE_WIDTH = 2

# A food cell tile: `scale` rows, each a list of Segments spanning `2*scale`
# columns. Kept as a type alias for readability at call sites.
FoodTile = list[list[Segment]]


def compute_layout(
    avail_cols: int, avail_rows: int, config: GameConfig
) -> tuple[int, int, int]:
    """Resolve ``(grid_width, grid_height, cell_scale)`` for the available space.

    A cell occupies ``CELL_BASE_WIDTH * k`` columns and ``k`` rows. The two modes
    are orthogonal: "cap" fixes the grid and derives the scale; "fill" fixes the
    scale and derives the grid. Grid dimensions are floored at `min_game_*` (a
    tiny terminal overflows rather than vanishing).
    """
    scale_setting = max(1, config.cell_scale)

    if config.sizing_mode == "fill":
        # Fixed cell size; the grid grows to fill the space.
        width = max(
            config.min_game_width, avail_cols // (CELL_BASE_WIDTH * scale_setting)
        )
        height = max(config.min_game_height, avail_rows // scale_setting)
        return width, height, scale_setting

    # "cap": fixed grid (clamped to the cap), cells grow up to `scale_setting`.
    width = max(
        config.min_game_width,
        min(config.max_grid_width, avail_cols // CELL_BASE_WIDTH),
    )
    height = max(
        config.min_game_height,
        min(config.max_grid_height, avail_rows),
    )
    fit = min(avail_cols // (CELL_BASE_WIDTH * width), avail_rows // height)
    scale = max(1, min(fit, scale_setting))
    return width, height, scale


def fit_grid_scale(
    avail_cols: int,
    avail_rows: int,
    grid_width: int,
    grid_height: int,
    max_scale: int,
) -> int:
    """Return the largest scale that fits an established logical grid.

    Scale never drops below one. If the viewport is smaller than the scale-one
    board, Textual may clip the rendering, but the logical game remains intact.
    """
    fit = min(
        avail_cols // (CELL_BASE_WIDTH * grid_width),
        avail_rows // grid_height,
    )
    return max(1, min(fit, max(1, max_scale)))


def glyph_food_tile(food_symbol: str, empty_cell: str, scale: int) -> FoodTile:
    """A food tile that centres the single themed glyph in its block.

    This is the unscaled look generalised to any scale, and the fallback when no
    sprite applies (notably scale 1, where the cell is too small for pixel art).
    """
    block_width = CELL_BASE_WIDTH * scale
    mid_row = scale // 2
    return [
        [Segment((food_symbol + " ").center(block_width))]
        if r == mid_row
        else [Segment(empty_cell * scale)]
        for r in range(scale)
    ]


def render_board(
    width: int,
    height: int,
    snake: set[Position],
    food: Position,
    scale: int,
    snake_block: str,
    empty_cell: str,
    food_tile: FoodTile,
) -> list[list[Segment]]:
    """Draw the board as Segments: one inner list per terminal row.

    Each logical cell becomes a ``(2*scale) x scale`` block. Snake and empty
    cells tile their base glyph (`snake_block` / `empty_cell`) and stay unstyled
    so they inherit the widget colour; the food cell uses `food_tile`, whose rows
    already span the block width and may carry their own styles.
    """
    snake_text = snake_block * scale
    empty_text = empty_cell * scale

    lines: list[list[Segment]] = []
    for y in range(height):
        block_rows: list[list[Segment]] = [[] for _ in range(scale)]
        for x in range(width):
            pos = (x, y)
            if pos in snake:
                for r in range(scale):
                    block_rows[r].append(Segment(snake_text))
            elif pos == food:
                for r in range(scale):
                    block_rows[r].extend(food_tile[r])
            else:
                for r in range(scale):
                    block_rows[r].append(Segment(empty_text))
        lines.extend(block_rows)
    return lines


def frame_board(
    lines: list[list[Segment]], board_cols: int, style: Style | None = None
) -> list[list[Segment]]:
    """Wrap rendered board rows in a box-drawing frame.

    Makes the play-area boundary explicit so that toroidal wrapping reads as
    "through the wall" rather than the snake splitting across empty margin. The
    framed block is `board_cols + 2` wide and two rows taller; callers draw it
    only when there's room to spare (i.e. the capped board sits inside a larger
    terminal — see `SnakeView`).
    """
    style = _BORDER_STYLE if style is None else style
    horizontal = "─" * board_cols
    framed: list[list[Segment]] = [[Segment(f"┌{horizontal}┐", style)]]
    side = Segment("│", style)
    for line in lines:
        framed.append([side, *line, side])
    framed.append([Segment(f"└{horizontal}┘", style)])
    return framed


def board_to_text(lines: list[list[Segment]]) -> str:
    """Flatten rendered Segment rows to plain text (styles dropped).

    Useful for asserting board dimensions/content without inspecting styles.
    """
    return "\n".join("".join(seg.text for seg in line) for line in lines)
