"""Pure helpers for sizing and drawing the board.

These are deliberately framework-free (no Textual widgets, no widget state) so the
layout maths and the board contents can be unit-tested directly. The board
decouples two quantities — the *logical grid* (game cells, which fix difficulty)
and the *visual scale* (characters per cell). `compute_layout` resolves both for
a fresh game's initial viewport according to the sizing mode:

- "cap": fix the grid (clamped to `max_grid_*`), then take the largest scale that
  fits up to `cell_scale` — a consistent, bounded board that may be letterboxed.
- "fill": fix the scale at `cell_scale`, then grow the grid to fill the space —
  fills the terminal, but the grid (and difficulty) vary with the window. A grid
  floored at `min_game_*` fits its scale down instead of being clipped.

Once play begins the logical grid is fixed. `fit_grid_scale` changes only the
visual scale as the viewport changes, so a terminal resize can never rewrite
snake or food coordinates.

With food sprites on, the scale never drops below `config.min_cell_scale` and cap
mode uses the grid cap exactly, so the food style and difficulty never depend on
the terminal. Where that board does not fit (`board_fits`), the view reports the
terminal too small instead of shrinking anything.

`render_board_row` turns one logical row of a game state into Rich `Segment`s (so individual cells can
carry their own colour — e.g. a food sprite). The food cell is supplied as a
pre-built *tile* so the board walker stays independent of how food is drawn:
`glyph_food_tile` keeps the single themed glyph; a sprite tile (see `sprites`)
swaps in pixel art. Both are `scale` rows tall and `2*scale` columns wide.

Between steps the view can interpolate motion. `motion_cells` works out which
cells are partly drawn at a given progress through a step: the head fills in
from the side it entered while the vacated tail cell drains towards the tail, so
the visible length stays constant. Near the end of a step the drawing leads a
little way into the next move (`lead_shift`). `partial_tile` draws such a cell
with block elements, and `render_board_row` draws those cells in place of whole
ones.
"""

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from rich.segment import Segment
from rich.style import Style

from .config import GameConfig
from .game_rules import Direction, GameRules, Position

# Subtle frame around the play area; dim so it reads as chrome, not as snake.
# No explicit colour, so it inherits the widget's colour (theme primary).
_BORDER_STYLE = Style(dim=True)
# With walls the frame is solid: heavy lines at full intensity.
_WALL_STYLE = Style()
# Box-drawing glyphs: top-left, top-right, bottom-left, bottom-right,
# horizontal, vertical.
_BORDER_GLYPHS = "┌┐└┘─│"
_WALL_GLYPHS = "┏┓┗┛━┃"
# Columns and rows a frame adds around the board: one edge on each side.
FRAME_MARGIN = 2

# A logical cell is drawn `CELL_BASE_WIDTH` columns wide by one row tall at
# scale 1. Terminal character cells are roughly twice as tall as wide, so two
# columns per cell makes a cell look square — the same trick the snake/empty
# glyphs ("██" / "  ") already rely on.
CELL_BASE_WIDTH = 2

# A food cell tile: `scale` rows, each a list of Segments spanning `2*scale`
# columns. Kept as a type alias for readability at call sites.
FoodTile = list[list[Segment]]

# A partly drawn snake cell: the side its filled part sits against, and how many
# of the cell's `motion_units(scale)` are filled from that side.
PartialCell = tuple[Direction, int]

# Partial cells are drawn with block elements: whole columns across, half rows
# up and down. They match the default snake and blank glyphs, which is what
# interpolation requires.
SMOOTH_SNAKE_BLOCK = "██"
SMOOTH_EMPTY_CELL = "  "

# Fraction of an increment within which a step's progress counts as on a
# substep boundary, matching the wake scheduled for it (`next_wake_delay`).
_BOUNDARY_TOLERANCE = 1e-6


@dataclass(frozen=True)
class Move:
    """One step's motion: the cell the head enters and the tail cell it leaves.

    `vacated` is None when the snake grows (the tail stays), and
    `vacated_heading` is None when a placed tail is not next to its segment.
    """

    head: Position
    heading: Direction
    vacated: Position | None = None
    vacated_heading: Direction | None = None


# No partly drawn cells: the board drawn whole.
_EMPTY_PARTIAL: dict[Position, PartialCell] = {}
NO_PARTIAL_CELLS: Final[Mapping[Position, PartialCell]] = MappingProxyType(
    _EMPTY_PARTIAL
)
_FULL = "█"
_UPPER_HALF = "▀"
_LOWER_HALF = "▄"


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
        # Fixed cell size; the grid grows to fill the space. Where the grid is
        # floored at its minimum, the cells shrink to fit it, as on a resize.
        width = max(
            config.min_game_width, avail_cols // (CELL_BASE_WIDTH * scale_setting)
        )
        height = max(config.min_game_height, avail_rows // scale_setting)
        scale = fit_grid_scale(
            avail_cols, avail_rows, width, height, scale_setting, config.min_cell_scale
        )
        return width, height, scale

    # "cap": fixed grid (clamped to the cap), cells grow up to `scale_setting`.
    # With sprites the cap is exact: a smaller terminal is too small, not a
    # reason for a smaller grid.
    if config.uses_sprites:
        width, height = config.max_grid_width, config.max_grid_height
    else:
        width = max(
            config.min_game_width,
            min(config.max_grid_width, avail_cols // CELL_BASE_WIDTH),
        )
        height = max(
            config.min_game_height,
            min(config.max_grid_height, avail_rows),
        )
    scale = fit_grid_scale(
        avail_cols, avail_rows, width, height, scale_setting, config.min_cell_scale
    )
    return width, height, scale


def fit_grid_scale(
    avail_cols: int,
    avail_rows: int,
    grid_width: int,
    grid_height: int,
    max_scale: int,
    min_scale: int = 1,
) -> int:
    """Return the largest scale that fits an established logical grid.

    Scale never drops below `min_scale` (one, or more with food sprites). If the
    viewport is smaller than the board at that scale, the rendering may be
    clipped (see `board_fits`), but the logical game remains intact.
    """
    fit = min(
        avail_cols // (CELL_BASE_WIDTH * grid_width),
        avail_rows // grid_height,
    )
    return max(min_scale, min(fit, max(1, max_scale)))


def board_size(grid_width: int, grid_height: int, scale: int) -> tuple[int, int]:
    """The ``(columns, rows)`` a grid occupies when drawn at `scale`."""
    return CELL_BASE_WIDTH * grid_width * scale, grid_height * scale


def board_fits(
    avail_cols: int, avail_rows: int, grid_width: int, grid_height: int, scale: int
) -> bool:
    """Whether a grid drawn at `scale` fits the available space."""
    cols, rows = board_size(grid_width, grid_height, scale)
    return cols <= avail_cols and rows <= avail_rows


def glyph_food_tile(
    food_symbol: str, empty_cell: str, scale: int, style: Style | None = None
) -> FoodTile:
    """A food tile that centres the single themed glyph in its block.

    This is the unscaled look generalised to any scale, and the fallback when no
    sprite applies (notably scale 1, where the cell is too small for pixel art).
    Without a `style` the glyph takes the board's colour.
    """
    block_width = CELL_BASE_WIDTH * scale
    mid_row = scale // 2
    return [
        [Segment((food_symbol + " ").center(block_width), style)]
        if r == mid_row
        else [Segment(empty_cell * scale)]
        for r in range(scale)
    ]


def motion_units(scale: int) -> int:
    """How many visible increments one step is drawn in at `scale`.

    A cell is ``2*scale`` columns wide and `scale` rows (``2*scale`` half rows)
    tall, so either axis moves in ``2*scale`` equal physical increments.
    """
    return CELL_BASE_WIDTH * scale


def partial_tile(anchor: Direction, filled: int, scale: int) -> FoodTile:
    """A snake cell with `filled` of its `motion_units` drawn against `anchor`.

    Horizontal anchors fill whole columns; vertical anchors fill half rows with
    upper and lower half blocks. Rows are unstyled, like whole snake cells, so
    they inherit the snake colour.
    """
    cols = CELL_BASE_WIDTH * scale
    if anchor in (Direction.LEFT, Direction.RIGHT):
        fill = _FULL * filled
        empty = " " * (cols - filled)
        text = fill + empty if anchor is Direction.LEFT else empty + fill
        return [[Segment(text)] for _ in range(scale)]
    rows: FoodTile = []
    for r in range(scale):
        # Half-row indices counted from the anchored edge.
        near, far = (2 * r, 2 * r + 1)
        if anchor is Direction.DOWN:
            near, far = (2 * (scale - 1 - r), 2 * (scale - 1 - r) + 1)
        upper, lower = (near < filled, far < filled)
        if anchor is Direction.DOWN:
            upper, lower = lower, upper
        glyph = _FULL if upper and lower else _UPPER_HALF if upper else _LOWER_HALF
        rows.append([Segment((glyph if upper or lower else " ") * cols)])
    return rows


def lead_shift(scale: int) -> int:
    """How many increments the drawing runs ahead of trailing by one step.

    An eighth of a cell's `motion_units`, rounded down: one column at scale 4 and
    none below it. The drawing trails the model, so after a key the head
    finishes its cell before the turn shows; leading shortens that run-on by the
    shift, but a key pressed during the lead swings it, pulling back what was
    drawn past the corner. A quarter cell (two columns at scale 4) swung visibly
    in play; see issue 0036.
    """
    return motion_units(scale) // 8


def motion_cells(
    taken: Move,
    progress: float,
    scale: int,
    upcoming: Move | None = None,
) -> dict[Position, PartialCell]:
    """The partly drawn cells `progress` of the way through a step.

    `taken` has already moved the model, and the drawing trails it: its head
    shows ``floor(progress * units) + 1 + lead_shift(scale)`` units filled from
    the side it entered, so a move shows at once, and its vacated cell keeps the
    rest against the side the tail moved towards. Once `taken` is drawn whole,
    the remaining units lead into `upcoming`, the move the next step will make
    (`Game.next_move()`; None if it would end the game, which is then not drawn
    ahead). A turn queued meanwhile swings that lead, at most `lead_shift` units.
    The visible length is constant, and a whole board needs no partial cells.

    A head moving into the cell its own tail is leaving stays whole.
    """
    units = motion_units(scale)
    filled = int(progress * units + _BOUNDARY_TOLERANCE) + 1 + lead_shift(scale)
    if filled < units:
        return _move_cells(taken, filled, units)
    if upcoming is None or filled == units:
        return {}
    return _move_cells(upcoming, min(filled - units, units - 1), units)


def _move_cells(move: Move, filled: int, units: int) -> dict[Position, PartialCell]:
    """`move` drawn with `filled` of its head cell's `units` filled."""
    if move.head == move.vacated:
        return {}
    cells = {move.head: (GameRules.get_opposite_direction(move.heading), filled)}
    if move.vacated is not None and move.vacated_heading is not None:
        cells[move.vacated] = (move.vacated_heading, units - filled)
    return cells


def render_board_row(
    width: int,
    y: int,
    snake: AbstractSet[Position],
    food: Position,
    scale: int,
    snake_block: str,
    empty_cell: str,
    food_tile: FoodTile,
    partial: Mapping[Position, PartialCell] = NO_PARTIAL_CELLS,
) -> list[list[Segment]]:
    """Draw logical row `y` as Segments: one inner list per terminal row.

    Each logical cell becomes a ``(2*scale) x scale`` block, so this returns
    `scale` terminal rows. Snake and empty cells tile their base glyph
    (`snake_block` / `empty_cell`) and stay unstyled so they inherit the widget
    colour; the food cell uses `food_tile`, whose rows already span the block
    width and may carry their own styles. Cells in `partial` are drawn part
    filled (see `partial_tile`), whatever else they hold.

    Each row is simplified so runs of same-style cells become one Segment. Textual
    emits a style reset and a full colour escape per Segment, so an uncoalesced
    row costs one escape pair per cell — most of the bytes written per frame.
    """
    snake_text = snake_block * scale
    empty_text = empty_cell * scale

    block_rows: list[list[Segment]] = [[] for _ in range(scale)]
    for x in range(width):
        pos = (x, y)
        if pos in partial:
            anchor, filled = partial[pos]
            for r, tile_row in enumerate(partial_tile(anchor, filled, scale)):
                block_rows[r].extend(tile_row)
        elif pos in snake:
            for r in range(scale):
                block_rows[r].append(Segment(snake_text))
        elif pos == food:
            for r in range(scale):
                block_rows[r].extend(food_tile[r])
        else:
            for r in range(scale):
                block_rows[r].append(Segment(empty_text))
    return [list(Segment.simplify(row)) for row in block_rows]


def render_board(
    width: int,
    height: int,
    snake: AbstractSet[Position],
    food: Position,
    scale: int,
    snake_block: str,
    empty_cell: str,
    food_tile: FoodTile,
) -> list[list[Segment]]:
    """Draw the whole board: `render_board_row` for every logical row."""
    return [
        line
        for y in range(height)
        for line in render_board_row(
            width, y, snake, food, scale, snake_block, empty_cell, food_tile
        )
    ]


def frame_board(
    lines: list[list[Segment]],
    board_cols: int,
    style: Style | None = None,
    *,
    walls: bool = False,
) -> list[list[Segment]]:
    """Wrap rendered board rows in a box-drawing frame.

    Makes the play-area boundary explicit. On a wrapping board the frame is dim,
    so the snake reads as passing "through the wall" rather than splitting across
    empty margin; with `walls` it is heavy and full intensity, a solid edge. The
    framed block is `board_cols + 2` wide and two rows taller; callers draw it
    only when there's room to spare (see `SnakeView`).
    """
    side = frame_side(style, walls=walls)
    return [
        [frame_rule(board_cols, top=True, style=style, walls=walls)],
        *([side, *line, side] for line in lines),
        [frame_rule(board_cols, top=False, style=style, walls=walls)],
    ]


def frame_rule(
    board_cols: int, *, top: bool, style: Style | None = None, walls: bool = False
) -> Segment:
    """The frame's top or bottom edge, `board_cols + 2` wide."""
    glyphs = _WALL_GLYPHS if walls else _BORDER_GLYPHS
    left, right = (glyphs[0], glyphs[1]) if top else (glyphs[2], glyphs[3])
    return Segment(f"{left}{glyphs[4] * board_cols}{right}", _frame_style(style, walls))


def frame_side(style: Style | None = None, *, walls: bool = False) -> Segment:
    """One vertical frame edge, drawn either side of every board row."""
    glyphs = _WALL_GLYPHS if walls else _BORDER_GLYPHS
    return Segment(glyphs[5], _frame_style(style, walls))


def _frame_style(style: Style | None, walls: bool) -> Style:
    if style is not None:
        return style
    return _WALL_STYLE if walls else _BORDER_STYLE


def board_to_text(lines: list[list[Segment]]) -> str:
    """Flatten rendered Segment rows to plain text (styles dropped).

    Useful for asserting board dimensions/content without inspecting styles.
    """
    return "\n".join("".join(seg.text for seg in line) for line in lines)
