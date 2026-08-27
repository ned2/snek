"""Tests for food sprites and the Segment tiles they render to."""

import pytest
from rich.cells import cell_len
from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment
from rich.style import Style

from snek import sprites


class TestSpriteRegistry:
    def test_default_sprite_exists(self):
        assert sprites.DEFAULT_SPRITE in sprites.SPRITES

    def test_every_world_resolves_to_a_known_sprite(self):
        """Level A maps every world (and wrap-arounds) to a registered sprite."""
        for world_index in range(20):  # well past the 8 worlds, exercises wrap
            assert sprites.get_food_sprite(world_index) in sprites.SPRITES


class TestFoodTile:
    def test_tile_shape_matches_cell_footprint(self):
        """A scale-k tile is k rows, each spanning 2k columns."""
        for scale in (2, 3, 4):
            tile = sprites.food_tile("apple", scale)
            assert len(tile) == scale
            widths = {sum(cell_len(seg.text) for seg in row) for row in tile}
            assert widths == {2 * scale}

    def test_tile_has_coloured_pixels(self):
        """The sprite actually draws something — some segments carry a style."""
        tile = sprites.food_tile("apple", 3)
        styled = [seg for row in tile for seg in row if seg.style is not None]
        assert styled

    def test_tile_is_cached(self):
        """Repeated builds for the same (sprite, scale) return the cached tile."""
        assert sprites.food_tile("apple", 3) is sprites.food_tile("apple", 3)

    def test_min_sprite_scale_is_above_one(self):
        """Scale 1 cells are too small for sprites; the floor must exclude them."""
        assert sprites.MIN_SPRITE_SCALE >= 2

    def test_tile_uses_the_rich_console_protocol(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The tile renderer needs only the public protocol exposed by Pixels."""

        class ProtocolOnlyPixels:
            def __rich_console__(
                self, _console: Console, _options: ConsoleOptions
            ) -> RenderResult:
                yield Segment("AB", Style(color="red"))
                yield Segment("\n")
                yield Segment("CD", Style(color="blue"))

        def fake_from_image(*_args: object, **_kwargs: object) -> ProtocolOnlyPixels:
            return ProtocolOnlyPixels()

        monkeypatch.setattr(sprites.Pixels, "from_image", fake_from_image)

        tile = sprites._build_tile(sprites.SPRITES["apple"], scale=2)

        assert [[segment.text for segment in row] for row in tile] == [
            ["AB"],
            ["CD"],
        ]
        assert [str(row[0].style) for row in tile] == ["red", "blue"]
