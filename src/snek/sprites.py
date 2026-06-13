"""Pixel-art food sprites and the Segment tiles they render to.

A sprite is a tiny character-keyed pixel grid plus an RGBA palette ('.' is
transparent and shows the board behind it). At render time the grid is built into
a PIL image and handed to rich-pixels, whose half-cell renderer packs two
vertical pixels into each character row using the ▄ glyph. A food cell at scale
`k` is `2*k` columns by `k` rows, so we resize the sprite to a `2k x 2k` pixel
image, which renders to exactly that tile (`k` rows of `2k` Segments).

Per the Level-A plan a single shared sprite is used for every world (see
`get_food_sprite`); per-world art slots in here later without touching callers.
Sprites only apply at scale >= `MIN_SPRITE_SCALE`: at scale 1 a food cell is just
2x1 characters, far too small for pixel art, so the caller falls back to the
themed glyph.
"""

from PIL import Image
from rich.segment import Segment
from rich_pixels import Pixels

from .rendering import FoodTile

# Below this scale a food cell can't hold a legible sprite; use the glyph instead.
MIN_SPRITE_SCALE = 2

_RGBA = tuple[int, int, int, int]
_TRANSPARENT: _RGBA = (0, 0, 0, 0)


class Sprite:
    """A pixel-art sprite: a palette and a grid of palette keys (one per pixel)."""

    def __init__(self, palette: dict[str, _RGBA], grid: list[str]) -> None:
        self.palette = palette
        self.grid = grid

    def image(self) -> Image.Image:
        """Build the base RGBA image (one pixel per grid character)."""
        height = len(self.grid)
        width = len(self.grid[0])
        img = Image.new("RGBA", (width, height), _TRANSPARENT)
        for y, row in enumerate(self.grid):
            for x, ch in enumerate(row):
                img.putpixel((x, y), self.palette[ch])
        return img


_APPLE = Sprite(
    palette={
        ".": _TRANSPARENT,
        "R": (210, 45, 55, 255),  # body
        "h": (255, 140, 140, 255),  # highlight
        "S": (110, 65, 30, 255),  # stem
        "L": (70, 175, 80, 255),  # leaf
    },
    grid=[
        "..SL..",
        ".RRRR.",
        "RhRRRR",
        "RRRRRR",
        "RRRRRR",
        ".RRRR.",
    ],
)

# The sprite registry. Level A ships one entry; A3 adds per-world art here.
SPRITES: dict[str, Sprite] = {"apple": _APPLE}
DEFAULT_SPRITE = "apple"

# Built tiles are cached per (sprite id, scale): there are only a handful of
# scales and sprites, and the result is reused every tick the food sits still.
_tile_cache: dict[tuple[str, int], FoodTile] = {}


def get_food_sprite(world_index: int) -> str:
    """The sprite id for a world. Level A: one shared sprite for every world."""
    return DEFAULT_SPRITE


def food_tile(sprite_id: str, scale: int) -> FoodTile:
    """Return the cached `k`-row x `2k`-column Segment tile for a sprite at `scale`."""
    key = (sprite_id, scale)
    tile = _tile_cache.get(key)
    if tile is None:
        tile = _build_tile(SPRITES[sprite_id], scale)
        _tile_cache[key] = tile
    return tile


def _build_tile(sprite: Sprite, scale: int) -> FoodTile:
    """Render a sprite to a food tile sized for `scale` (a 2k x 2k px image)."""
    side = 2 * scale
    pixels = Pixels.from_image(sprite.image(), resize=(side, side))
    return [list(line) for line in Segment.split_lines(pixels._segments.segments)]
