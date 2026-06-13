"""Tests for the framework-free board sizing and drawing helpers."""

from snek.config import GameConfig
from snek.rendering import compute_grid_size, compute_scale, render_board


class TestComputeGridSize:
    """The logical grid is clamped to [min_game_*, max_grid_*]."""

    def test_typical_terminal_lands_on_the_cap(self):
        """An 80x24-class space (≈48 cols after the panel) gets the full cap."""
        cfg = GameConfig()
        assert compute_grid_size(48, 24, cfg) == (
            cfg.max_grid_width,
            cfg.max_grid_height,
        )

    def test_large_terminal_is_capped_not_grown(self):
        """A huge terminal does not enlarge the logical grid past the cap."""
        cfg = GameConfig()
        assert compute_grid_size(400, 120, cfg) == (
            cfg.max_grid_width,
            cfg.max_grid_height,
        )

    def test_small_terminal_shrinks_below_the_cap(self):
        """When the cap won't fit at scale 1 the grid shrinks toward it."""
        cfg = GameConfig()
        # 30 cols -> 15 cells wide; 8 rows -> floored at min_game_height.
        assert compute_grid_size(30, 8, cfg) == (15, cfg.min_game_height)

    def test_tiny_terminal_floors_at_minimum(self):
        """Below the minimum the grid stops shrinking (may overflow, never vanish)."""
        cfg = GameConfig()
        assert compute_grid_size(4, 2, cfg) == (
            cfg.min_game_width,
            cfg.min_game_height,
        )


class TestComputeScale:
    """The visual scale is the largest integer that fits, floored at 1, capped."""

    def test_small_terminal_is_scale_one(self):
        cfg = GameConfig()
        assert compute_scale(48, 24, 20, 15, cfg) == 1

    def test_medium_terminal_scales_up(self):
        cfg = GameConfig()
        # ≈120-col terminal (88 usable) x 30 rows fits two cells per axis-unit.
        assert compute_scale(88, 30, 20, 15, cfg) == 2

    def test_large_terminal_is_capped(self):
        cfg = GameConfig()
        assert compute_scale(400, 120, 20, 15, cfg) == cfg.max_cell_scale

    def test_never_below_one(self):
        """A space too small for even scale 1 still reports 1, not 0."""
        cfg = GameConfig()
        assert compute_scale(10, 5, 20, 15, cfg) == 1


class TestRenderBoard:
    """`render_board` expands each cell to a (2*scale) x scale block."""

    def _split(self, text: str) -> list[str]:
        return text.split("\n")

    def test_scale_one_dimensions_and_content(self):
        lines = self._split(
            render_board(
                width=3,
                height=2,
                snake={(0, 0)},
                food=(2, 1),
                food_symbol="X",
                snake_block="██",
                empty_cell="  ",
                scale=1,
            )
        )
        assert len(lines) == 2  # height * scale
        assert all(len(line) == 6 for line in lines)  # width * 2 * scale
        assert lines[0] == "██    "  # snake cell then two empty cells
        assert lines[1] == "    X "  # two empty cells then centred food

    def test_scale_three_dimensions(self):
        scale = 3
        lines = self._split(
            render_board(
                width=4,
                height=2,
                snake={(0, 0)},
                food=(3, 1),
                food_symbol="X",
                snake_block="██",
                empty_cell="  ",
                scale=scale,
            )
        )
        assert len(lines) == 2 * scale
        assert all(len(line) == 4 * 2 * scale for line in lines)

    def test_scale_three_snake_cell_is_a_solid_block(self):
        scale = 3
        lines = self._split(
            render_board(
                width=2,
                height=1,
                snake={(0, 0)},
                food=(1, 0),
                food_symbol="X",
                snake_block="██",
                empty_cell="  ",
                scale=scale,
            )
        )
        # All `scale` rows of the snake cell are full blocks of width 2*scale.
        block = "█" * (2 * scale)
        assert all(line.startswith(block) for line in lines)

    def test_scale_three_food_is_centred_in_its_block(self):
        scale = 3
        lines = self._split(
            render_board(
                width=1,
                height=1,
                snake=set(),
                food=(0, 0),
                food_symbol="X",
                snake_block="██",
                empty_cell="  ",
                scale=scale,
            )
        )
        # Only the middle row carries the glyph; the others are blank.
        assert lines[0].strip() == ""
        assert "X" in lines[scale // 2]
        assert lines[-1].strip() == ""

    def test_empty_board_is_all_spaces(self):
        text = render_board(
            width=3,
            height=3,
            snake=set(),
            food=(-1, -1),  # off-board: nothing drawn
            food_symbol="X",
            snake_block="██",
            empty_cell="  ",
            scale=2,
        )
        assert text.strip() == ""
