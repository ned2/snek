"""The glyph sets the snake can be drawn with, and how a pixel mask becomes text.

The snake is drawn in pixels finer than a terminal character, so that it can be
narrower than its cell (see `rendering.snake_tile`). A glyph set divides each
character into a small grid of pixels and has a glyph for every pattern of lit
pixels:

- "sextants": 2x3 pixels a character, from Unicode 13's Symbols for Legacy
  Computing;
- "octants": 2x4, from Unicode 16, the finest but the least widely drawn;
- "half-blocks": 1x2 (▀ ▄ █), which every terminal draws.

A character's pixels are numbered row by row, left to right, and a pattern is the
bit mask of its lit pixels (bit i for pixel i). Unicode orders the sextant and
octant blocks by that pattern, leaving out the patterns other blocks already
draw, so each table is built by walking its block and filling those gaps.

Framework-free, like `rendering`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class GlyphSet:
    """A glyph for every pattern of lit pixels in a `columns` x `rows` character."""

    columns: int
    rows: int
    # Indexed by pattern: bit i set means pixel i (row by row) is lit.
    glyphs: str

    def encode(self, lit: Sequence[Sequence[bool]]) -> list[str]:
        """The lines of text that draw a grid of pixels, given row by row.

        The grid must be a whole number of characters wide and high.
        """
        lines: list[str] = []
        for top in range(0, len(lit), self.rows):
            band = lit[top : top + self.rows]
            line: list[str] = []
            for left in range(0, len(band[0]), self.columns):
                pattern = 0
                for r, row in enumerate(band):
                    for c in range(self.columns):
                        if row[left + c]:
                            pattern |= 1 << (r * self.columns + c)
                line.append(self.glyphs[pattern])
            lines.append("".join(line))
        return lines


def _block(first: int, pixels: int, elsewhere: Mapping[int, str]) -> str:
    """Glyphs for every pattern of `pixels` pixels, from a block in pattern order.

    The block starts at code point `first` and skips the patterns in `elsewhere`,
    which gives their glyphs from other blocks.
    """
    glyphs: list[str] = []
    code = first
    for pattern in range(1 << pixels):
        if pattern in elsewhere:
            glyphs.append(elsewhere[pattern])
        else:
            glyphs.append(chr(code))
            code += 1
    return "".join(glyphs)


# Patterns the sextant block (U+1FB00) leaves out.
_SEXTANTS_ELSEWHERE: Final = {
    0b000000: " ",
    0b010101: "▌",
    0b101010: "▐",
    0b111111: "█",
}

# Patterns the octant block (U+1CD00) leaves out. Code points are escaped, since
# Python before 3.13 has no names for Unicode 16's.
_OCTANTS_ELSEWHERE: Final = {
    0b00000000: " ",
    0b00000001: "\U0001cea8",  # LEFT HALF UPPER ONE QUARTER BLOCK
    0b00000010: "\U0001ceab",  # RIGHT HALF UPPER ONE QUARTER BLOCK
    0b00000011: "\U0001fb82",  # UPPER ONE QUARTER BLOCK
    0b00000101: "▘",
    0b00001010: "▝",
    0b00001111: "▀",
    0b00010100: "\U0001fbe6",  # MIDDLE LEFT ONE QUARTER BLOCK
    0b00101000: "\U0001fbe7",  # MIDDLE RIGHT ONE QUARTER BLOCK
    0b00111111: "\U0001fb85",  # UPPER THREE QUARTERS BLOCK
    0b01000000: "\U0001cea3",  # LEFT HALF LOWER ONE QUARTER BLOCK
    0b01010000: "▖",
    0b01010101: "▌",
    0b01011010: "▞",
    0b01011111: "▛",
    0b10000000: "\U0001cea0",  # RIGHT HALF LOWER ONE QUARTER BLOCK
    0b10100000: "▗",
    0b10100101: "▚",
    0b10101010: "▐",
    0b10101111: "▜",
    0b11000000: "▂",
    0b11110000: "▄",
    0b11110101: "▙",
    0b11111010: "▟",
    0b11111100: "▆",
    0b11111111: "█",
}

# The snake's glyph sets by name, in the order the settings offer them. The first
# is the default.
SNAKE_GLYPH_SETS: Final[Mapping[str, GlyphSet]] = {
    "sextants": GlyphSet(2, 3, _block(0x1FB00, 6, _SEXTANTS_ELSEWHERE)),
    "octants": GlyphSet(2, 4, _block(0x1CD00, 8, _OCTANTS_ELSEWHERE)),
    "half-blocks": GlyphSet(1, 2, " ▀▄█"),
}
