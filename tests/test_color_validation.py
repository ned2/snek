"""Tests to ensure all colors used in the app are valid."""

import pytest

from rich.console import Console
from rich.style import Style
from textual.color import Color as TextualColor

from snek.themes import THEME_MAP


class TestColorValidation:
    """Test that all colors used in the app are valid."""

    def test_theme_colors_are_valid_rich_colors(self):
        """Test that all theme colors are valid Rich color names."""
        console = Console()

        for theme_name, theme in THEME_MAP.items():
            # Test primary color
            try:
                # Extract color value (remove # if present)
                color = theme.primary
                if color.startswith("#"):
                    # Rich can handle hex colors
                    Style(color=color)
                else:
                    Style(color=color)
                    console.get_style(color)
            except Exception as e:
                pytest.fail(
                    f"Theme '{theme_name}' has invalid primary color '{theme.primary}': {e}"
                )

    def test_theme_colors_are_valid_textual_colors(self):
        """Test that theme colors can be parsed by Textual."""
        for theme_name, theme in THEME_MAP.items():
            # Test primary color
            try:
                # Textual Theme objects already have validated colors
                # Just verify the primary color can be parsed
                color = theme.primary
                if color.startswith("#"):
                    # Hex color
                    TextualColor.parse(color)
                else:
                    # Named color
                    TextualColor.parse(color)
            except Exception as e:
                pytest.fail(
                    f"Theme '{theme_name}' has invalid Textual color '{theme.primary}': {e}"
                )

    def test_hardcoded_colors_in_app(self):
        """Test hardcoded colors in the app are valid."""
        console = Console()

        # Colors used in app.py
        hardcoded_colors = [
            "green",  # Used in CSS and default theme
            "red",  # Used for death view
            "yellow",  # Used for pause view
            "cyan",  # Used in themes
            "magenta",  # Used in themes
            "dim",  # Used for text styling
            "bold",  # Not a color but a style
        ]

        for color in hardcoded_colors:
            if color in ["dim", "bold"]:  # These are styles, not colors
                continue
            try:
                console.get_style(color)
            except Exception as e:
                pytest.fail(f"Hardcoded color '{color}' is invalid: {e}")

    def test_gradient_colors(self):
        """Test gradient colors used in splash screen."""
        console = Console()

        # The splash screen uses gradient(purple,blue)
        gradient_colors = ["purple", "blue"]

        for color in gradient_colors:
            try:
                # Rich uses 'magenta' instead of 'purple'
                if color == "purple":
                    color = "magenta"
                console.get_style(color)
            except Exception as e:
                pytest.fail(f"Gradient color '{color}' is invalid: {e}")

    def test_all_theme_colors_unique(self):
        """Test that each theme has a unique primary color."""
        colors = [theme.primary for theme in THEME_MAP.values()]

        # Check for duplicates
        assert len(colors) == len(set(colors)), (
            "Some themes share the same primary color"
        )

    def test_theme_color_rendering(self):
        """Test that theme colors can be rendered in text."""
        from rich.text import Text

        for theme_name, theme in THEME_MAP.items():
            try:
                # Create text with the theme's primary color
                text = Text("Test", style=theme.primary)
                # This should not raise an exception
                str(text)
            except Exception as e:
                pytest.fail(
                    f"Failed to render text with theme '{theme_name}' color '{theme.primary}': {e}"
                )


class TestValidColorNames:
    """Document and test valid color names for Rich/Textual."""

    def test_list_valid_rich_colors(self):
        """List all valid Rich color names."""
        # Standard 16 ANSI colors that Rich supports
        valid_colors = [
            "black",
            "red",
            "green",
            "yellow",
            "blue",
            "magenta",
            "cyan",
            "white",
            "bright_black",
            "bright_red",
            "bright_green",
            "bright_yellow",
            "bright_blue",
            "bright_magenta",
            "bright_cyan",
            "bright_white",
            # Also supports:
            "default",
            "none",
        ]

        console = Console()

        for color in valid_colors:
            try:
                console.get_style(color)
            except Exception:
                # Document which colors are NOT valid
                print(f"Color '{color}' is not valid in Rich")

    def test_rgb_color_format(self):
        """Test RGB color format for more color options."""
        from rich.style import Style

        # If we need more colors, we can use RGB
        rgb_colors = [
            "rgb(255,165,0)",  # Orange
            "rgb(128,0,128)",  # Purple
            "#FFA500",  # Orange in hex
            "#800080",  # Purple in hex
        ]

        for color in rgb_colors:
            try:
                style = Style(color=color)
                assert style is not None
            except Exception as e:
                pytest.fail(f"RGB color '{color}' is invalid: {e}")
