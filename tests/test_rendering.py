"""Tests for the framework-free board sizing and drawing helpers."""

import unicodedata
from itertools import pairwise

import pytest
from rich.cells import cell_len
from rich.style import Style

from snek.config import GameConfig
from snek.game_rules import Direction, GameRules, Position
from snek.rendering import (
    JOIN_DOWN,
    JOIN_RIGHT,
    bezel_corner,
    bezel_rule,
    board_fits,
    board_size,
    board_to_text,
    cell_pixels,
    compute_layout,
    fit_grid_scale,
    frame_board,
    glyph_food_tile,
    motion_cells,
    motion_units,
    render_board,
    render_board_row,
    snake_joins,
    snake_tile,
)
from snek.snake_glyphs import SNAKE_GLYPH_SETS, GlyphSet

# Half blocks keep expected text readable: a pixel is a column by half a row.
HALF = SNAKE_GLYPH_SETS["half-blocks"]
SEXTANTS = SNAKE_GLYPH_SETS["sextants"]
OCTANTS = SNAKE_GLYPH_SETS["octants"]


def _render(width, height, snake, food, food_symbol, scale):
    """Render a glyph-food board to plain text, the snake in half blocks.

    `snake` lists the snake's cells in body order.
    """
    tile = glyph_food_tile(food_symbol, "  ", scale)
    joins = snake_joins(list(snake), width, height)
    lines = render_board(width, height, joins, food, scale, HALF, "  ", tile)
    return board_to_text(lines)


def _pixels(lines: list[str], glyphs: GlyphSet) -> list[list[bool]]:
    """Decode drawn text back to its grid of lit pixels."""
    grid: list[list[bool]] = []
    for line in lines:
        patterns = [glyphs.glyphs.index(ch) for ch in line]
        for r in range(glyphs.rows):
            grid.append(
                [
                    bool(pattern >> (r * glyphs.columns + c) & 1)
                    for pattern in patterns
                    for c in range(glyphs.columns)
                ]
            )
    return grid


def _tile_pixels(tile, glyphs: GlyphSet) -> list[list[bool]]:
    return _pixels(["".join(seg.text for seg in row) for row in tile], glyphs)


class TestComputeLayoutCapMode:
    """'cap' mode: fixed grid (clamped), scale derived (largest that fits, capped)."""

    def _cfg(self, **kw):
        kw.setdefault("cell_scale", 3)  # room to scale up
        return GameConfig(sizing_mode="cap", **kw)

    def test_large_terminal_lands_on_cap_and_scales(self):
        cfg = self._cfg()
        w, h, k = compute_layout(200, 60, cfg)
        assert (w, h) == (cfg.max_grid_width, cfg.max_grid_height)
        assert k >= 1

    def test_grid_not_grown_past_cap(self):
        cfg = self._cfg()
        w, h, _ = compute_layout(400, 120, cfg)
        assert (w, h) == (cfg.max_grid_width, cfg.max_grid_height)

    def test_scale_capped_at_cell_scale(self):
        cfg = self._cfg()
        _, _, k = compute_layout(4000, 4000, cfg)
        assert k == cfg.cell_scale

    def test_small_terminal_shrinks_grid_and_scale_one(self):
        cfg = self._cfg()
        # 30 cols -> 15 cells wide; 8 rows floored at min_game_height; scale 1.
        assert compute_layout(30, 8, cfg) == (15, cfg.min_game_height, 1)

    def test_tiny_terminal_floors_at_minimum(self):
        cfg = self._cfg()
        assert compute_layout(4, 2, cfg) == (
            cfg.min_game_width,
            cfg.min_game_height,
            1,
        )


class TestComputeLayoutWithSprites:
    """With food sprites, cells never drop below scale two and cap is exact."""

    def _cfg(self, **kw):
        kw.setdefault("cell_scale", 3)
        return GameConfig(food_type="sprites", **kw)

    def test_cap_uses_the_whole_cap_on_a_small_terminal(self):
        """No smaller grid: the view reports the terminal too small instead."""
        cfg = self._cfg()
        assert compute_layout(80, 24, cfg) == (
            cfg.max_grid_width,
            cfg.max_grid_height,
            2,
        )

    def test_cap_still_scales_up_to_cell_scale(self):
        cfg = self._cfg()
        assert compute_layout(4000, 4000, cfg)[2] == cfg.cell_scale

    def test_fill_keeps_its_exact_scale(self):
        cfg = self._cfg(sizing_mode="fill", cell_scale=2)
        assert compute_layout(142, 48, cfg) == (35, 24, 2)


class TestComputeLayoutFillMode:
    """'fill' mode: fixed scale, grid grows to fill the space."""

    def test_grid_fills_at_scale_one(self):
        cfg = GameConfig(sizing_mode="fill", cell_scale=1)
        # Each cell is 2 cols x 1 row at scale 1.
        assert compute_layout(142, 48, cfg) == (71, 48, 1)

    def test_grid_fills_at_scale_two(self):
        cfg = GameConfig(sizing_mode="fill", cell_scale=2)
        # Each cell is 4 cols x 2 rows at scale 2.
        assert compute_layout(142, 48, cfg) == (35, 24, 2)

    def test_scale_is_fixed_not_grown(self):
        """Even on a huge terminal, fill keeps the requested scale."""
        cfg = GameConfig(sizing_mode="fill", cell_scale=2)
        _, _, k = compute_layout(4000, 4000, cfg)
        assert k == 2

    def test_floors_at_minimum_grid(self):
        """A floored grid shrinks its cells to fit rather than being clipped."""
        cfg = GameConfig(sizing_mode="fill", cell_scale=3)
        assert compute_layout(4, 2, cfg) == (
            cfg.min_game_width,
            cfg.min_game_height,
            1,
        )

    def test_floored_grid_fits_the_largest_scale_that_fits(self):
        """80x24 leaves a 50x24 view: 10x10 cells fit at scale two, not three."""
        cfg = GameConfig(sizing_mode="fill", cell_scale=3, food_type="sprites")
        assert compute_layout(50, 24, cfg) == (10, 10, 2)

    def test_floored_grid_keeps_the_sprite_floor(self):
        cfg = GameConfig(sizing_mode="fill", cell_scale=3, food_type="sprites")
        assert compute_layout(4, 2, cfg)[2] == 2


class TestFitGridScale:
    """An established logical grid is only visually fitted to new viewports."""

    def test_grows_and_shrinks_without_changing_grid_inputs(self):
        assert fit_grid_scale(216, 60, 36, 20, 3) == 3
        assert fit_grid_scale(144, 40, 36, 20, 3) == 2
        assert fit_grid_scale(72, 20, 36, 20, 3) == 1

    def test_too_small_viewport_still_uses_scale_one(self):
        """Clipping is safer than corrupting model coordinates."""
        assert fit_grid_scale(10, 4, 36, 20, 3) == 1

    def test_scale_respects_configured_ceiling(self):
        assert fit_grid_scale(10_000, 10_000, 20, 10, 2) == 2

    def test_scale_respects_a_floor(self):
        """With sprites the floor is two, even where only scale one fits."""
        assert fit_grid_scale(72, 20, 36, 20, 3, min_scale=2) == 2
        assert fit_grid_scale(216, 60, 36, 20, 3, min_scale=2) == 3


class TestBoardFits:
    def test_board_size_is_two_columns_and_one_row_per_scale(self):
        assert board_size(36, 20, 2) == (144, 40)

    def test_fits_exactly_but_not_one_short(self):
        assert board_fits(144, 40, 36, 20, 2)
        assert not board_fits(143, 40, 36, 20, 2)
        assert not board_fits(144, 39, 36, 20, 2)


class TestRenderBoard:
    """`render_board` expands each cell to a (2*scale) x scale block of Segments."""

    def _split(self, text: str) -> list[str]:
        return text.split("\n")

    def test_returns_segment_rows(self):
        """The board is Segment rows, not a string; text flattens for assertions."""
        tile = glyph_food_tile("X", "  ", 1)
        lines = render_board(2, 1, {(0, 0): 0}, (1, 0), 1, HALF, "  ", tile)
        assert isinstance(lines, list)
        assert all(isinstance(seg.text, str) for line in lines for seg in line)

    def test_scale_one_dimensions_and_content(self):
        lines = self._split(_render(3, 2, [(0, 0)], (2, 1), "X", 1))
        assert len(lines) == 2  # height * scale
        assert all(len(line) == 6 for line in lines)  # width * 2 * scale
        assert lines[0] == "▀     "  # snake cell then two empty cells
        assert lines[1] == "    X "  # two empty cells then centred food

    def test_scale_three_dimensions(self):
        scale = 3
        lines = self._split(_render(4, 2, [(0, 0)], (3, 1), "X", scale))
        assert len(lines) == 2 * scale
        assert all(len(line) == 4 * 2 * scale for line in lines)

    def test_scale_three_snake_cell_leaves_a_gap_right_and_below(self):
        scale = 3
        lines = self._split(_render(2, 1, [(0, 0)], (1, 0), "X", scale))
        # 6x6 pixels with a quarter (rounded, 2) left unlit on the right and below.
        assert [line[:6] for line in lines] == ["████  ", "████  ", "      "]

    def test_scale_three_food_is_centred_in_its_block(self):
        scale = 3
        lines = self._split(_render(1, 1, [], (0, 0), "X", scale))
        # Only the middle row carries the glyph; the others are blank.
        assert lines[0].strip() == ""
        assert "X" in lines[scale // 2]
        assert lines[-1].strip() == ""

    def test_same_style_cells_coalesce_into_one_segment_per_run(self):
        """Adjacent unstyled cells merge, so each row emits few style escapes."""
        tile = glyph_food_tile("X", "  ", 2)
        joins = {(0, 0): JOIN_RIGHT, (1, 0): 0}
        lines = render_board(5, 1, joins, (-1, -1), 2, HALF, "  ", tile)
        # Snake and empty cells are both unstyled, so each row is a single run.
        assert all(len(line) == 1 for line in lines)
        assert board_to_text(lines).split("\n")[0] == "█" * 7 + " " * 13

    def test_empty_board_is_all_spaces(self):
        # Off-board food: nothing drawn.
        text = _render(3, 3, [], (-1, -1), "X", 2)
        assert text.strip() == ""


class TestFrameBoard:
    """`frame_board` wraps the board in a box-drawing frame."""

    def _framed_text(self, width, height, scale):
        tile = glyph_food_tile("X", "  ", scale)
        lines = render_board(width, height, {}, (-1, -1), scale, HALF, "  ", tile)
        board_cols = 2 * width * scale
        return board_to_text(frame_board(lines, board_cols)).split("\n")

    def test_adds_two_rows_and_two_columns(self):
        # 3x2 board at scale 1 -> 2 rows x 6 cols, framed -> 4 rows x 8 cols.
        rows = self._framed_text(3, 2, 1)
        assert len(rows) == 2 + 2
        assert all(len(r) == 6 + 2 for r in rows)

    def test_corners_and_edges(self):
        rows = self._framed_text(3, 2, 1)
        assert rows[0] == "┌──────┐"
        assert rows[-1] == "└──────┘"
        for r in rows[1:-1]:
            assert r[0] == "│" and r[-1] == "│"

    def test_walls_draw_a_solid_heavy_frame(self):
        tile = glyph_food_tile("X", "  ", 1)
        lines = render_board(3, 2, {}, (-1, -1), 1, HALF, "  ", tile)
        framed = frame_board(lines, 6, walls=True)
        rows = board_to_text(framed).split("\n")
        assert rows[0] == "┏━━━━━━┓"
        assert rows[-1] == "┗━━━━━━┛"
        for r in rows[1:-1]:
            assert r[0] == "┃" and r[-1] == "┃"
        # Full intensity, unlike the dim frame of a wrapping board.
        assert not framed[0][0].style.dim
        assert frame_board(lines, 6)[0][0].style.dim


class TestBezelRule:
    """`bezel_rule` draws a bezel's top and bottom edges round a frame."""

    def test_half_blocks_with_empty_corners(self):
        style = Style(color="#c7f0d8")
        top = bezel_rule(8, top=True, style=style)
        bottom = bezel_rule(8, top=False, style=style)
        assert top.text == " " + "▄" * 8 + " "
        assert bottom.text == " " + "▀" * 8 + " "
        assert top.style == bottom.style == style

    def test_corners_step_in_round_the_frame(self):
        """Each corner block lacks the quadrant at the bezel's outer corner."""
        style = Style(color="#c7f0d8")
        corners = [
            bezel_corner(top=top, left=left, style=style).text
            for top in (True, False)
            for left in (True, False)
        ]
        assert corners == ["▟", "▙", "▜", "▛"]


class TestSnakeGlyphs:
    """Each glyph set has one glyph a pattern, and draws the pattern it's indexed by."""

    @pytest.mark.parametrize("name", SNAKE_GLYPH_SETS)
    def test_one_distinct_single_width_glyph_per_pattern(self, name):
        glyphs = SNAKE_GLYPH_SETS[name]
        assert len(glyphs.glyphs) == 1 << (glyphs.columns * glyphs.rows)
        assert len(set(glyphs.glyphs)) == len(glyphs.glyphs)
        assert all(cell_len(glyph) == 1 for glyph in glyphs.glyphs)

    @pytest.mark.skipif(
        unicodedata.unidata_version < "16", reason="needs Unicode 16 names"
    )
    @pytest.mark.parametrize(
        ("glyphs", "prefix"),
        [(SEXTANTS, "BLOCK SEXTANT-"), (OCTANTS, "BLOCK OCTANT-")],
    )
    def test_named_glyphs_light_the_pixels_their_names_give(self, glyphs, prefix):
        named = 0
        for pattern, glyph in enumerate(glyphs.glyphs):
            name = unicodedata.name(glyph)
            if name.startswith(prefix):
                digits = name.removeprefix(prefix)
                assert pattern == sum(1 << (int(d) - 1) for d in digits)
                named += 1
        assert named == {SEXTANTS: 60, OCTANTS: 230}[glyphs]

    def test_encode_packs_pixels_into_characters(self):
        lit = [[True, False, False, True], [True, True, False, True]]
        assert HALF.encode(lit) == ["█▄ █"]
        assert _pixels(OCTANTS.encode(lit * 2), OCTANTS) == lit * 2


class TestSnakeJoins:
    """Each cell records the joins across its own right and bottom gaps."""

    def test_joins_follow_body_order(self):
        snake = [(2, 1), (1, 1), (1, 0), (2, 0)]
        assert snake_joins(snake, 5, 5) == {
            (2, 1): 0,
            (1, 1): JOIN_RIGHT,
            (1, 0): JOIN_DOWN | JOIN_RIGHT,
            (2, 0): 0,
        }

    def test_side_by_side_cells_that_are_not_consecutive_stay_apart(self):
        # A U-turn: (0, 0) and (0, 1) touch but are the snake's two ends.
        joins = snake_joins([(0, 0), (1, 0), (1, 1), (0, 1)], 5, 5)
        assert not joins[0, 0] & JOIN_DOWN

    def test_segments_join_across_a_wrapping_edge(self):
        joins = snake_joins([(0, 2), (4, 2), (4, 3), (4, 4), (4, 0)], 5, 5)
        assert joins[4, 2] & JOIN_RIGHT
        assert joins[4, 4] & JOIN_DOWN

    def test_a_single_cell_has_no_joins(self):
        assert snake_joins([(3, 3)], 5, 5) == {(3, 3): 0}


def _lit_box(grid: list[list[bool]]) -> tuple[int, int]:
    """The (columns, rows) lit from the top-left of a cell's pixel grid."""
    return sum(grid[0]), sum(row[0] for row in grid)


class TestSnakeTile:
    """A snake cell is lit but for a quarter-cell gap, filled where it joins."""

    @pytest.mark.parametrize("name", SNAKE_GLYPH_SETS)
    @pytest.mark.parametrize("scale", [1, 2, 3])
    def test_an_unjoined_cell_leaves_a_quarter_on_its_right_and_bottom(
        self, name, scale
    ):
        glyphs = SNAKE_GLYPH_SETS[name]
        columns, rows = cell_pixels(scale, glyphs)
        tile = snake_tile(glyphs, scale, 0)
        assert len(tile) == scale
        grid = _tile_pixels(tile, glyphs)
        assert (len(grid[0]), len(grid)) == (columns, rows)
        lit_columns, lit_rows = _lit_box(grid)
        for length, lit in ((columns, lit_columns), (rows, lit_rows)):
            gap = length - lit
            assert gap >= 1
            assert abs(gap - length / 4) <= 0.5
        assert all(
            grid[r][c] == (c < lit_columns and r < lit_rows)
            for r in range(rows)
            for c in range(columns)
        )

    def test_nokia_cell_is_three_pixels_of_four(self):
        """Octants at scale 1 and half blocks at scale 2 are Nokia's 4x4 cell."""
        for glyphs, scale in ((OCTANTS, 1), (HALF, 2)):
            grid = _tile_pixels(snake_tile(glyphs, scale, 0), glyphs)
            assert cell_pixels(scale, glyphs) == (4, 4)
            assert _lit_box(grid) == (3, 3)

    @pytest.mark.parametrize("name", SNAKE_GLYPH_SETS)
    def test_joins_fill_the_gap_but_never_the_corner(self, name):
        glyphs = SNAKE_GLYPH_SETS[name]
        lone = _tile_pixels(snake_tile(glyphs, 2, 0), glyphs)
        lit_columns, lit_rows = _lit_box(lone)
        right = _tile_pixels(snake_tile(glyphs, 2, JOIN_RIGHT), glyphs)
        down = _tile_pixels(snake_tile(glyphs, 2, JOIN_DOWN), glyphs)
        both = _tile_pixels(snake_tile(glyphs, 2, JOIN_RIGHT | JOIN_DOWN), glyphs)
        assert _lit_box(right) == (len(right[0]), lit_rows)
        assert _lit_box(down) == (lit_columns, len(down))
        assert not both[-1][-1]
        assert both == [
            [a or b for a, b in zip(r, d, strict=True)]
            for r, d in zip(right, down, strict=True)
        ]

    @pytest.mark.parametrize("anchor", list(Direction))
    def test_clipped_cell_keeps_only_the_anchored_pixels(self, anchor):
        whole = _tile_pixels(snake_tile(OCTANTS, 1, JOIN_RIGHT | JOIN_DOWN), OCTANTS)
        for filled in range(5):
            tile = snake_tile(OCTANTS, 1, JOIN_RIGHT | JOIN_DOWN, ((anchor, filled),))
            grid = _tile_pixels(tile, OCTANTS)
            for r in range(4):
                for c in range(4):
                    inside = {
                        Direction.LEFT: c < filled,
                        Direction.RIGHT: c >= 4 - filled,
                        Direction.UP: r < filled,
                        Direction.DOWN: r >= 4 - filled,
                    }[anchor]
                    assert grid[r][c] == (whole[r][c] and inside)


def test_runs_side_by_side_show_a_gap_while_the_body_stays_joined():
    """The reason for the gap: a U-turn's two runs are told apart."""
    snake: list[Position] = [(0, 0), (1, 0), (2, 0), (2, 1), (1, 1), (0, 1)]
    joins = snake_joins(snake, 3, 2)
    tile = glyph_food_tile("X", "  ", 1)
    for glyphs in SNAKE_GLYPH_SETS.values():
        lines = render_board(3, 2, joins, (-1, -1), 1, glyphs, "  ", tile)
        grid = _pixels(board_to_text(lines).split("\n"), glyphs)
        columns, rows = cell_pixels(1, glyphs)
        # The pixel row just above the second run, under the first, stays dark
        # except under the turn at the right, where the body joins.
        between = grid[rows - 1]
        lit_columns = _lit_box(_tile_pixels(snake_tile(glyphs, 1, 0), glyphs))[0]
        turn = slice(2 * columns, 2 * columns + lit_columns)
        assert all(between[turn])
        assert not any(between[: turn.start] + between[turn.stop :])


_STEP = {
    Direction.RIGHT: (1, 0),
    Direction.LEFT: (-1, 0),
    Direction.DOWN: (0, 1),
    Direction.UP: (0, -1),
}


def _board_pixels(snake, partial, glyphs, scale, size=7):
    """The lit pixels of a `size`-square board, the snake given in body order."""
    joins = snake_joins(snake, size, size)
    tile = glyph_food_tile("X", "  ", scale)
    lines = [
        "".join(seg.text for seg in row)
        for y in range(size)
        for row in render_board_row(
            size, y, joins, (-1, -1), scale, glyphs, "  ", tile, partial
        )
    ]
    return _pixels(lines, glyphs)


def _extreme(grid, direction: Direction) -> int:
    """How far the lit pixels reach in `direction`."""
    xs = [c for row in grid for c, on in enumerate(row) if on]
    ys = [r for r, row in enumerate(grid) if any(row)]
    return {
        Direction.RIGHT: max(xs),
        Direction.LEFT: -min(xs),
        Direction.DOWN: max(ys),
        Direction.UP: -min(ys),
    }[direction]


def _slide(glyphs, scale, before, heading, tail_heading=None):
    """How far the head tip and the tail end move at each drawing of one step.

    `before` is the snake before the step, head first; the drawings run from it
    whole, through every increment, to the snake after the step drawn whole.
    """
    dx, dy = _STEP[heading]
    head = (before[0][0] + dx, before[0][1] + dy)
    after = [head, *before[:-1]]
    vacated = before[-1]
    if tail_heading is None:
        tail_heading = GameRules.direction_between(vacated, after[-1], 7, 7)
    back = GameRules.get_opposite_direction(tail_heading)
    units = motion_units(scale, glyphs)
    grids = [_board_pixels(before, {}, glyphs, scale)]
    for index in range(units - 1):
        partial = motion_cells(
            head, heading, vacated, tail_heading, index / units, scale, glyphs, 7, 7
        )
        body = [*after, vacated] if vacated in partial else after
        grids.append(_board_pixels(body, partial, glyphs, scale))
    grids.append(_board_pixels(after, {}, glyphs, scale))
    tips = [_extreme(grid, heading) for grid in grids]
    ends = [-_extreme(grid, back) for grid in grids]
    return (
        [b - a for a, b in pairwise(tips)],
        [b - a for a, b in pairwise(ends)],
    )


class TestMotionCells:
    """Each end of the snake slides a pixel an increment, gaps included."""

    @pytest.mark.parametrize("name", SNAKE_GLYPH_SETS)
    @pytest.mark.parametrize("scale", [1, 2, 3])
    @pytest.mark.parametrize("heading", list(Direction))
    def test_both_ends_slide_evenly_in_every_direction(self, name, scale, heading):
        glyphs = SNAKE_GLYPH_SETS[name]
        dx, dy = _STEP[heading]
        before = [(3 - i * dx, 3 - i * dy) for i in range(3)]
        columns, rows = cell_pixels(scale, glyphs)
        length = columns if dx else rows
        for moves in _slide(glyphs, scale, before, heading):
            assert sum(moves) == length
            if length == motion_units(scale, glyphs):
                assert moves == [1] * length
            else:
                # Fewer pixels than increments: never more than one at a time.
                assert set(moves) <= {0, 1}

    @pytest.mark.parametrize("name", SNAKE_GLYPH_SETS)
    @pytest.mark.parametrize(
        ("before", "heading"),
        [
            ([(3, 3)], Direction.RIGHT),  # one cell: the join is in the old cell
            ([(3, 3)], Direction.LEFT),
            ([(3, 3), (4, 3)], Direction.DOWN),  # neck and new tail are one cell
            ([(3, 3), (3, 4)], Direction.RIGHT),
        ],
    )
    def test_short_snakes_cut_a_cell_from_both_ends(self, name, before, heading):
        glyphs = SNAKE_GLYPH_SETS[name]
        tail = heading if len(before) == 1 else None
        for moves in _slide(glyphs, 2, before, heading, tail):
            assert set(moves) <= {0, 1}
            assert sum(moves) > 0

    def test_one_increment_a_pixel_across(self):
        assert motion_units(1, HALF) == 2
        assert motion_units(1, OCTANTS) == motion_units(1, SEXTANTS) == 4
        assert motion_units(3, OCTANTS) == 12

    def test_the_head_cell_fills_from_the_side_it_entered(self):
        """Moving left the join is the head's own, drawn first."""
        cells = motion_cells(
            (5, 5), Direction.LEFT, (8, 5), Direction.LEFT, 0.0, 1, OCTANTS, 10, 10
        )
        assert cells[5, 5] == ((Direction.RIGHT, 1),)

    def test_moving_right_the_join_into_the_head_is_drawn_first(self):
        """The join is the neck's gap: it fills before any of the head shows."""
        cells = motion_cells(
            (5, 5), Direction.RIGHT, (2, 5), Direction.RIGHT, 0.0, 2, OCTANTS, 10, 10
        )
        # 8 pixels across, a 2-pixel gap: the neck's 6, then 1 of its join.
        assert cells[4, 5] == ((Direction.LEFT, 7),)
        assert cells[5, 5] == ((Direction.LEFT, 0),)

    def test_a_substep_boundary_counts_despite_rounding(self):
        """Progress a hair under a boundary (float error) draws that increment."""
        cells = motion_cells(
            (6, 5),
            Direction.LEFT,
            (9, 5),
            Direction.LEFT,
            3 / 8 - 1e-12,
            4,
            HALF,
            20,
            20,
        )
        assert cells[6, 5] == ((Direction.RIGHT, 4),)

    def test_growth_has_no_vacated_cell(self):
        cells = motion_cells((6, 5), Direction.LEFT, None, None, 0.0, 2, HALF, 20, 20)
        assert cells == {(6, 5): ((Direction.RIGHT, 1),)}

    def test_head_entering_its_own_vacated_tail_cell_stays_whole(self):
        cells = motion_cells(
            (5, 5), Direction.UP, (5, 5), Direction.LEFT, 0.0, 2, HALF, 20, 20
        )
        assert cells == {}

    def test_progress_at_or_past_the_step_is_drawn_whole(self):
        cells = motion_cells(
            (6, 5), Direction.RIGHT, (5, 5), Direction.RIGHT, 1.0, 3, HALF, 20, 20
        )
        assert cells == {}

    def test_joins_wrap_with_the_board(self):
        """Moving right off the edge, the neck on the far side holds the join."""
        cells = motion_cells(
            (0, 5), Direction.RIGHT, None, None, 0.0, 2, OCTANTS, 10, 10
        )
        assert (9, 5) in cells


def test_render_board_row_draws_partial_cells_over_the_board():
    """Partial cells replace the head's snake cell and the empty vacated cell.

    The vacated cell keeps its join to the new tail while it drains.
    """
    partial = {(2, 0): ((Direction.LEFT, 1),), (1, 0): ((Direction.RIGHT, 1),)}
    joins = {(1, 0): JOIN_RIGHT, (2, 0): 0}
    tile = glyph_food_tile("*", "  ", 1)
    rows = render_board_row(4, 0, joins, (3, 0), 1, HALF, "  ", tile, partial)
    assert board_to_text(rows) == "   ▀▀ * "
