"""Tests for the framework-free board sizing and drawing helpers."""

from snek.config import GameConfig
from snek.rendering import (
    board_to_text,
    compute_layout,
    frame_board,
    glyph_food_tile,
    render_board,
)


def _render(width, height, snake, food, food_symbol, scale):
    """Render a glyph-food board to plain text (test convenience)."""
    tile = glyph_food_tile(food_symbol, "  ", scale)
    lines = render_board(width, height, snake, food, scale, "██", "  ", tile)
    return board_to_text(lines)


class TestComputeLayoutCapMode:
    """'cap' mode: fixed grid (clamped), scale derived (largest that fits, capped)."""

    def _cfg(self, **kw):
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
        cfg = GameConfig(sizing_mode="fill", cell_scale=3)
        assert compute_layout(4, 2, cfg) == (
            cfg.min_game_width,
            cfg.min_game_height,
            3,
        )


class TestRenderBoard:
    """`render_board` expands each cell to a (2*scale) x scale block of Segments."""

    def _split(self, text: str) -> list[str]:
        return text.split("\n")

    def test_returns_segment_rows(self):
        """The board is Segment rows, not a string; text flattens for assertions."""
        tile = glyph_food_tile("X", "  ", 1)
        lines = render_board(2, 1, {(0, 0)}, (1, 0), 1, "██", "  ", tile)
        assert isinstance(lines, list)
        assert all(isinstance(seg.text, str) for line in lines for seg in line)

    def test_scale_one_dimensions_and_content(self):
        lines = self._split(_render(3, 2, {(0, 0)}, (2, 1), "X", 1))
        assert len(lines) == 2  # height * scale
        assert all(len(line) == 6 for line in lines)  # width * 2 * scale
        assert lines[0] == "██    "  # snake cell then two empty cells
        assert lines[1] == "    X "  # two empty cells then centred food

    def test_scale_three_dimensions(self):
        scale = 3
        lines = self._split(_render(4, 2, {(0, 0)}, (3, 1), "X", scale))
        assert len(lines) == 2 * scale
        assert all(len(line) == 4 * 2 * scale for line in lines)

    def test_scale_three_snake_cell_is_a_solid_block(self):
        scale = 3
        lines = self._split(_render(2, 1, {(0, 0)}, (1, 0), "X", scale))
        # All `scale` rows of the snake cell are full blocks of width 2*scale.
        block = "█" * (2 * scale)
        assert all(line.startswith(block) for line in lines)

    def test_scale_three_food_is_centred_in_its_block(self):
        scale = 3
        lines = self._split(_render(1, 1, set(), (0, 0), "X", scale))
        # Only the middle row carries the glyph; the others are blank.
        assert lines[0].strip() == ""
        assert "X" in lines[scale // 2]
        assert lines[-1].strip() == ""

    def test_empty_board_is_all_spaces(self):
        # Off-board food: nothing drawn.
        text = _render(3, 3, set(), (-1, -1), "X", 2)
        assert text.strip() == ""


class TestFrameBoard:
    """`frame_board` wraps the board in a box-drawing frame."""

    def _framed_text(self, width, height, scale):
        tile = glyph_food_tile("X", "  ", scale)
        lines = render_board(width, height, set(), (-1, -1), scale, "██", "  ", tile)
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
