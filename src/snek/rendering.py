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

The snake is drawn narrower than its cells, like Nokia Snake's: `snake_tile`
draws a cell in pixels finer than a character (see `snake_glyphs`), lighting the
cell but for a gap along its right and bottom edges, which it fills only where
it joins the next segment. Runs of the snake that lie side by side stay apart,
while the body reads as one piece. `snake_joins` works out those joins from the
snake's order.

Between steps the view can interpolate motion. `motion_cells` works out which
cells are partly drawn at a given progress through a step: the head fills in
from the side it entered while the vacated tail cell drains towards the tail, so
the visible length stays constant. `snake_tile` clips such a cell from that
side (and the neighbour holding the join, if that is still moving), and
`render_board_row` draws those cells in place of whole ones.
"""

from collections.abc import Mapping, Sequence
from functools import lru_cache
from itertools import pairwise
from types import MappingProxyType
from typing import Final

from rich.segment import Segment
from rich.style import Style

from .config import GameConfig
from .game_rules import Direction, GameRules, Position
from .snake_glyphs import GlyphSet

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
# Columns and rows a bezel adds around the frame: one edge on each side.
BEZEL_MARGIN = 2
# A bezel's top and bottom edges are half-cell blocks, so the edge is about as
# thick as the one-column sides. Each corner steps in over two cells: the edge's
# corner cell is empty and the side cell beside the frame's corner is a
# three-quadrant block, so the corner curves round as far as the bezel is thick.
_BEZEL_TOP = " ▄ "
_BEZEL_BOTTOM = " ▀ "
# The side cells beside the frame's corners: (top, bottom) by (left, right).
_BEZEL_CORNERS = {True: "▟▙", False: "▜▛"}

# A logical cell is drawn `CELL_BASE_WIDTH` columns wide by one row tall at
# scale 1. Terminal character cells are roughly twice as tall as wide, so two
# columns per cell makes a cell look square — the same trick the snake/empty
# glyphs ("██" / "  ") already rely on.
CELL_BASE_WIDTH = 2

# A food cell tile: `scale` rows, each a list of Segments spanning `2*scale`
# columns. Kept as a type alias for readability at call sites.
FoodTile = list[list[Segment]]

# A cut through a partly drawn snake cell: the side its drawn part sits against,
# and how many of the cell's pixels (see `cell_pixels`) are drawn from that side.
Clip = tuple[Direction, int]

# A partly drawn snake cell: the clips that cut it. All of them apply, since a
# short snake's cell can be cut from both ends at once.
PartialCell = tuple[Clip, ...]

# A snake cell's joins: which of its gaps, right and bottom, it fills to join the
# segment beyond. A cell's left and top joins are its neighbours' to draw.
JOIN_RIGHT: Final = 1
JOIN_DOWN: Final = 2

# Partial cells leave the unfilled part blank, so interpolation needs the default
# blank glyph.
SMOOTH_EMPTY_CELL = "  "

# Fraction of an increment within which a step's progress counts as on a
# substep boundary, matching the wake scheduled for it (`next_wake_delay`).
_BOUNDARY_TOLERANCE = 1e-6

# No partly drawn cells: the board drawn whole.
_EMPTY_PARTIAL: dict[Position, PartialCell] = {}
NO_PARTIAL_CELLS: Final[Mapping[Position, PartialCell]] = MappingProxyType(
    _EMPTY_PARTIAL
)


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


def cell_pixels(scale: int, glyphs: GlyphSet) -> tuple[int, int]:
    """The ``(columns, rows)`` of pixels a snake cell is drawn in at `scale`."""
    return CELL_BASE_WIDTH * scale * glyphs.columns, scale * glyphs.rows


def _gap(pixels: int) -> int:
    """The gap beside a snake cell `pixels` long: a quarter, like Nokia's.

    Nokia Snake drew 3 pixels of each 4-pixel cell. Rounded to the nearest pixel,
    and never less than one, so runs side by side always stay apart.
    """
    return max(1, (pixels + 2) // 4)


@lru_cache(maxsize=1024)
def snake_tile(
    glyphs: GlyphSet, scale: int, joins: int, clips: PartialCell = ()
) -> FoodTile:
    """A snake cell: lit but for a gap on its right and bottom, filled where it joins.

    `joins` holds `JOIN_RIGHT` and `JOIN_DOWN`. Each of `clips` keeps only that
    many pixels from its anchored side, as the cell fills or drains during a
    step. Rows are unstyled, so they take the snake's colour.
    """
    columns, rows = cell_pixels(scale, glyphs)
    lit_columns, lit_rows = columns - _gap(columns), rows - _gap(rows)
    right, down = bool(joins & JOIN_RIGHT), bool(joins & JOIN_DOWN)
    lit = [
        [
            (c < lit_columns or right) and (r < lit_rows or (down and c < lit_columns))
            for c in range(columns)
        ]
        for r in range(rows)
    ]
    for anchor, filled in clips:
        for r in range(rows):
            for c in range(columns):
                inside = {
                    Direction.LEFT: c < filled,
                    Direction.RIGHT: c >= columns - filled,
                    Direction.UP: r < filled,
                    Direction.DOWN: r >= rows - filled,
                }[anchor]
                lit[r][c] = lit[r][c] and inside
    return [[Segment(line)] for line in glyphs.encode(lit)]


def snake_joins(
    snake: Sequence[Position], width: int, height: int
) -> dict[Position, int]:
    """Each snake cell's joins (see `snake_tile`), from the cells in body order.

    Wrap-aware: segments either side of a wrapping edge join across it, so the
    cell on the right or bottom edge fills its gap against the edge.
    """
    joins = dict.fromkeys(snake, 0)
    for cell, beyond in pairwise(snake):
        direction = GameRules.direction_between(cell, beyond, width, height)
        if direction is Direction.RIGHT:
            joins[cell] |= JOIN_RIGHT
        elif direction is Direction.LEFT:
            joins[beyond] |= JOIN_RIGHT
        elif direction is Direction.DOWN:
            joins[cell] |= JOIN_DOWN
        elif direction is Direction.UP:
            joins[beyond] |= JOIN_DOWN
    return joins


def motion_units(scale: int, glyphs: GlyphSet) -> int:
    """How many visible increments one step is drawn in at `scale`.

    One a pixel across the cell. Every glyph set has at least as many pixels
    across a cell as down it, so a step down moves at most a pixel an increment.
    """
    return cell_pixels(scale, glyphs)[0]


def _pixels_filled(units_filled: int, units: int, pixels: int) -> int:
    """Pixels to draw for `units_filled` of `units`, along an axis `pixels` long.

    The nearest pixel, rounding halves up, so increments stay as even as the
    pixels allow on an axis with fewer pixels than increments.
    """
    return (2 * units_filled * pixels + units) // (2 * units)


def motion_cells(
    head: Position,
    heading: Direction,
    vacated: Position | None,
    vacated_heading: Direction | None,
    progress: float,
    scale: int,
    glyphs: GlyphSet,
    width: int,
    height: int,
) -> dict[Position, PartialCell]:
    """The partly drawn cells `progress` of the way through a step.

    The step has already moved the model: `head` is its new head and `vacated`
    its old tail cell (None when the snake grew), on a `width` x `height` board.
    The drawing trails the model by up to one step. The front of the snake has
    moved ``floor(progress * units) + 1`` of the step's `motion_units`, so a move
    shows at once, and its back the same; each is converted to pixels along its
    own axis.

    Each end slides a pixel an increment, gap included. A cell's join sits in
    its own right or bottom gap (see `snake_tile`), so moving right or down the
    head's join is in the neck and is drawn first, before the head's own pixels;
    moving left or up the vacated cell's join is in the new tail and is drawn
    away last. The visible length is constant, and a fully drawn step needs no
    partial cells.

    A head moving into the cell its own tail just left stays whole.
    """
    units = motion_units(scale, glyphs)
    filled = min(units, int(progress * units + _BOUNDARY_TOLERANCE) + 1)
    if filled >= units or head == vacated:
        return {}
    columns, rows = cell_pixels(scale, glyphs)
    clips: dict[Position, list[Clip]] = {}

    def clip(cell: Position, anchor: Direction, pixels: int) -> None:
        clips.setdefault(cell, []).append((anchor, pixels))

    length = columns if heading in (Direction.LEFT, Direction.RIGHT) else rows
    gap = _gap(length)
    moved = max(1, _pixels_filled(filled, units, length))
    back = GameRules.get_opposite_direction(heading)
    if heading in (Direction.RIGHT, Direction.DOWN):
        neck = GameRules.calculate_new_position(head, back, width, height)
        if moved < gap:
            clip(neck, back, length - gap + moved)
        clip(head, back, max(0, moved - gap))
    else:
        clip(head, back, moved)

    if vacated is not None and vacated_heading is not None:
        across = vacated_heading in (Direction.LEFT, Direction.RIGHT)
        length = columns if across else rows
        gap = _gap(length)
        left = length - _pixels_filled(filled, units, length)
        if vacated_heading in (Direction.RIGHT, Direction.DOWN):
            clip(vacated, vacated_heading, left)
        else:
            tail = GameRules.calculate_new_position(
                vacated, vacated_heading, width, height
            )
            clip(vacated, vacated_heading, max(0, left - gap))
            if left < gap:
                clip(tail, vacated_heading, length - gap + left)
    return {cell: tuple(cuts) for cell, cuts in clips.items()}


def render_board_row(
    width: int,
    y: int,
    snake: Mapping[Position, int],
    food: Position,
    scale: int,
    glyphs: GlyphSet,
    empty_cell: str,
    food_tile: FoodTile,
    partial: Mapping[Position, PartialCell] = NO_PARTIAL_CELLS,
) -> list[list[Segment]]:
    """Draw logical row `y` as Segments: one inner list per terminal row.

    Each logical cell becomes a ``(2*scale) x scale`` block, so this returns
    `scale` terminal rows. `snake` maps each snake cell to its joins (see
    `snake_joins`), and snake cells are drawn with `glyphs` (see `snake_tile`).
    Snake and empty cells (tiling `empty_cell`) stay unstyled so they inherit
    the widget colour; the food cell uses `food_tile`, whose rows already span
    the block width and may carry their own styles. Cells in `partial` are drawn
    part filled, with their joins in `snake` if they have any, whatever else
    they hold.

    Each row is simplified so runs of same-style cells become one Segment. Textual
    emits a style reset and a full colour escape per Segment, so an uncoalesced
    row costs one escape pair per cell — most of the bytes written per frame.
    """
    empty_text = empty_cell * scale

    block_rows: list[list[Segment]] = [[] for _ in range(scale)]
    for x in range(width):
        pos = (x, y)
        if pos in partial:
            tile = snake_tile(glyphs, scale, snake.get(pos, 0), partial[pos])
        elif pos in snake:
            tile = snake_tile(glyphs, scale, snake[pos])
        elif pos == food:
            tile = food_tile
        else:
            for r in range(scale):
                block_rows[r].append(Segment(empty_text))
            continue
        for r in range(scale):
            block_rows[r].extend(tile[r])
    return [list(Segment.simplify(row)) for row in block_rows]


def render_board(
    width: int,
    height: int,
    snake: Mapping[Position, int],
    food: Position,
    scale: int,
    glyphs: GlyphSet,
    empty_cell: str,
    food_tile: FoodTile,
) -> list[list[Segment]]:
    """Draw the whole board: `render_board_row` for every logical row."""
    return [
        line
        for y in range(height)
        for line in render_board_row(
            width, y, snake, food, scale, glyphs, empty_cell, food_tile
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


def bezel_rule(frame_cols: int, *, top: bool, style: Style) -> Segment:
    """A bezel's top or bottom edge, `frame_cols + 2` wide.

    The blocks are drawn in `style`'s colour (the bezel's) on whatever lies
    behind them, and the corner cells are left empty (see `bezel_corner`). The
    bezel's other side cells are plain cells in its background colour.
    """
    left, fill, right = _BEZEL_TOP if top else _BEZEL_BOTTOM
    return Segment(f"{left}{fill * frame_cols}{right}", style)


def bezel_corner(*, top: bool, left: bool, style: Style) -> Segment:
    """The bezel's side cell beside one of the frame's corners.

    A three-quadrant block in `style`'s colour, missing the quadrant at the
    bezel's outer corner: with the empty corner cell of `bezel_rule` it rounds
    that corner off.
    """
    return Segment(_BEZEL_CORNERS[top][0 if left else 1], style)


def board_to_text(lines: list[list[Segment]]) -> str:
    """Flatten rendered Segment rows to plain text (styles dropped).

    Useful for asserting board dimensions/content without inspecting styles.
    """
    return "\n".join("".join(seg.text for seg in line) for line in lines)
