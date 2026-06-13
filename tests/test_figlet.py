"""Tests for the in-repo `FigletText` widget.

Each test guards a behavior that broke during the migration off `textual-pyfiglet`:
pyfiglet's default-width wrapping, the gradient endpoints, and the scroll seam.
"""

import pytest
from pyfiglet import figlet_format
from textual.color import Color

from snek.app import SnakeApp
from snek.figlet import FigletText

# The fonts/text actually used across the app's call sites.
CALL_SITES = [
    ("SNEK", "doh"),
    ("PAUSED", "doom"),
    ("GAME OVER", "doom"),
    ("SNEK", "small"),
]


def _distance(a: Color, b: Color) -> int:
    """Manhattan distance between two colors in RGB space."""
    return sum(abs(x - y) for x, y in zip(a.rgb, b.rgb))


@pytest.mark.parametrize("text, font", CALL_SITES)
def test_art_is_not_internally_wrapped(text: str, font: str) -> None:
    """pyfiglet's default width=80 splits wide fonts; we must lay glyphs on one line."""
    widget = FigletText(text, font=font)
    wide = figlet_format(text, font=font, width=10_000).rstrip("\n").split("\n")
    assert widget._lines == wide


def test_doh_title_would_wrap_at_default_width() -> None:
    """Regression: the `doh` SNEK splash wrapped `K` onto a second block at width 80."""
    wrapped = figlet_format("SNEK", font="doh").rstrip("\n").split("\n")
    ours = FigletText("SNEK", font="doh")._lines
    # The default-width render is taller because it folds the letters; ours stays compact.
    assert len(ours) < len(wrapped)


def test_solid_color_applies_to_every_row() -> None:
    """A single color fills the whole art."""
    widget = FigletText("PAUSED", font="doom", colors=["#ff00ff"])
    colors = [Color.parse("#ff00ff")]
    n = len(widget._lines)
    styles = [widget._line_style(colors, None, i, n) for i in range(n)]
    assert all(s.color == Color.parse("#ff00ff").rich_color for s in styles)


def test_gradient_is_cyclic() -> None:
    """The gradient must loop (first color repeated as the last stop) for seamless scroll."""
    colors = [Color.parse("#00ff00"), Color.parse("#2a2a2a")]
    gradient = FigletText._build_gradient(colors)
    assert gradient is not None
    assert gradient.get_color(0.0).rgb == gradient.get_color(1.0).rgb == (0, 255, 0)


def test_gradient_static_endpoints() -> None:
    """At rest the art reads first-color (top) to last-color (bottom)."""
    primary, panel = Color.parse("#00ff00"), Color.parse("#2a2a2a")
    widget = FigletText("SNEK", font="doh", colors=["#00ff00", "#2a2a2a"], animate=True)
    gradient = FigletText._build_gradient([primary, panel])
    n = len(widget._lines)
    top = widget._line_style([primary, panel], gradient, 0, n).color
    bottom = widget._line_style([primary, panel], gradient, n - 1, n).color
    top = Color.from_rich_color(top)
    bottom = Color.from_rich_color(bottom)
    assert top.rgb == (0, 255, 0)
    assert _distance(bottom, panel) < _distance(bottom, primary)


def test_scroll_has_no_seam() -> None:
    """Regression: a non-cyclic gradient jumped dark->bright at the wrap each frame."""
    primary, panel = Color.parse("#00ff00"), Color.parse("#2a2a2a")
    widget = FigletText("SNEK", font="doh", colors=["#00ff00", "#2a2a2a"], animate=True)
    gradient = FigletText._build_gradient([primary, panel])
    n = len(widget._lines)

    def max_adjacent_delta() -> int:
        rows = [
            Color.from_rich_color(
                widget._line_style([primary, panel], gradient, i, n).color
            )
            for i in range(n)
        ]
        return max(_distance(rows[i], rows[i + 1]) for i in range(n - 1))

    # Across a full cycle the largest row-to-row jump must stay small (no seam spike).
    for frame in range(50):
        widget._offset = frame / 50
        assert max_adjacent_delta() < 40


@pytest.mark.asyncio
async def test_theme_token_resolution_and_live_recolor() -> None:
    """`$primary` resolves to the active theme and follows when the theme changes."""
    app = SnakeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        title = app.screen.query_one("#splash-title", FigletText)

        classic_primary = Color.parse(app.theme_variables["primary"])
        assert title._resolve_colors()[0].rgb == classic_primary.rgb

        # Switch to another world's theme; resolution must follow live.
        app.theme = "snek-ocean"
        await pilot.pause()
        ocean_primary = Color.parse(app.theme_variables["primary"])
        assert title._resolve_colors()[0].rgb == ocean_primary.rgb
        assert ocean_primary.rgb != classic_primary.rgb


@pytest.mark.asyncio
async def test_title_does_not_wrap_in_layout() -> None:
    """The mounted splash title is its natural art height, not a wrapped multiple."""
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        title = app.screen.query_one("#splash-title", FigletText)
        assert title.region.height == len(title._lines)
