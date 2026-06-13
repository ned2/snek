"""A thin in-repo figlet widget built on `pyfiglet` and Textual.

Replaces the third-party ``textual_pyfiglet.FigletWidget`` (and its dependency stack,
which capped us at ``textual<6``). ``FigletText`` renders text as figlet ASCII-art via
``pyfiglet`` and applies a theme-aware solid color or vertical gradient, optionally
animated. See ``issues/0001-pyfiglet-abstraction/`` for the design.
"""

from pyfiglet import figlet_format
from rich.style import Style
from rich.text import Text
from textual.color import Color, Gradient
from textual.timer import Timer
from textual.widgets import Static

# Fraction of the gradient scrolled per animation frame, and the animation frame rate.
_ANIMATION_STEP = 0.02
_ANIMATION_FPS = 12

# pyfiglet wraps the rendered letters at this column count (default 80), which splits wide
# fonts like `doh` across rows. We lay every glyph out on one line and let Textual handle
# fitting the art to the terminal.
_FIGLET_WIDTH = 10_000


class FigletText(Static):
    """Figlet-rendered text with an optional theme-aware color or vertical gradient.

    Args:
        text: The string to render as figlet art.
        font: Any pyfiglet font name (e.g. ``doh``, ``doom``, ``small``).
        colors: Color strings and/or Textual theme tokens (``"$primary"``). ``None``/empty
            inherits the widget color; one entry fills solid; two or more interpolate as a
            vertical gradient across the glyph rows.
        animate: When ``True`` and ``colors`` has two or more entries, scroll the gradient
            vertically. Ignored otherwise.
    """

    # Size to the fixed-width art (`width: auto`). Call sites must not force a width
    # narrower than the art, or Textual reflows the glyph rows onto new lines.
    DEFAULT_CSS = "FigletText { width: auto; height: auto; }"

    def __init__(
        self,
        text: str,
        *,
        font: str = "standard",
        colors: list[str] | None = None,
        animate: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__("", name=name, id=id, classes=classes)
        self._colors = colors or []
        self._animate = animate and len(self._colors) >= 2
        self._offset = 0.0
        self._timer: Timer | None = None
        # Text and font are fixed for this app's call sites, so render the art once.
        self._lines = (
            figlet_format(text, font=font, width=_FIGLET_WIDTH).rstrip("\n").split("\n")
        )

    def on_mount(self) -> None:
        """Build the colored renderable and start the animation if enabled."""
        self._rebuild()
        if self._animate:
            self._timer = self.set_interval(1 / _ANIMATION_FPS, self._tick)

    def on_unmount(self) -> None:
        """Stop the animation timer if one is running."""
        if self._timer is not None:
            self._timer.stop()

    def notify_style_update(self) -> None:
        """Re-resolve theme tokens when the stylesheet or app theme changes.

        Textual calls this after (re)applying styles — including on `app.theme`
        switches — so the baked-in figlet colors recolor live without
        subscribing to `theme_changed_signal`. The game swaps themes per world,
        so persistent titles depend on this. The animation timer is unaffected.
        """
        super().notify_style_update()
        self._rebuild()

    def _tick(self) -> None:
        """Advance the gradient scroll by one frame."""
        self._offset = (self._offset + _ANIMATION_STEP) % 1.0
        self._rebuild()

    def _resolve_colors(self) -> list[Color]:
        """Resolve color strings / theme tokens to `Color` objects."""
        resolved: list[Color] = []
        for color in self._colors:
            if color.startswith("$"):
                color = self.app.theme_variables[color[1:]]
            resolved.append(Color.parse(color))
        return resolved

    def _rebuild(self) -> None:
        """Render the figlet lines into a styled `Text` and update the widget."""
        colors = self._resolve_colors()
        rendered = Text()
        gradient = self._build_gradient(colors)
        line_count = len(self._lines)
        for index, line in enumerate(self._lines):
            style = self._line_style(colors, gradient, index, line_count)
            rendered.append(line, style=style)
            if index < line_count - 1:
                rendered.append("\n")
        self.update(rendered)

    @staticmethod
    def _build_gradient(colors: list[Color]) -> Gradient | None:
        """Build a *cyclic* gradient, or `None` if fewer than two colors.

        The first color is repeated as the final stop so the gradient loops seamlessly:
        scrolling past the end ramps smoothly back to the start instead of jumping. The
        visible rows only ever cover the first ``(N-1)/N`` of the cycle (see `_line_style`);
        the closing segment is the off-screen ramp that scrolls in during animation.
        """
        count = len(colors)
        if count < 2:
            return None
        cyclic = [*colors, colors[0]]
        return Gradient(*((index / count, color) for index, color in enumerate(cyclic)))

    def _line_style(
        self,
        colors: list[Color],
        gradient: Gradient | None,
        index: int,
        line_count: int,
    ) -> Style:
        """Pick the color style for a single art row."""
        if gradient is not None:
            # Map rows across the first (N-1)/N of the cyclic gradient so a static render
            # shows colors[0]..colors[-1] in order, leaving the loop-back segment hidden.
            window = (len(colors) - 1) / len(colors)
            position = index / (line_count - 1) if line_count > 1 else 0.0
            position = (position * window + self._offset) % 1.0
            color = gradient.get_color(position)
            return Style(color=color.rich_color)
        if colors:
            return Style(color=colors[0].rich_color)
        return Style()
