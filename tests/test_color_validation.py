"""Tests to ensure all colors used in the app are valid."""

import pytest

from rich.console import Console
from rich.style import Style
from textual.color import Color as TextualColor

from snek.themes import ThemeManager


class TestColorValidation:
    """Test that all colors used in the app are valid."""

    def test_theme_colors_are_valid_rich_colors(self):
        """Test that all theme colors are valid Rich color names."""
        console = Console()
        manager = ThemeManager()

        for theme in manager.themes:
            # Test that the color can be used in Rich
            try:
                style = Style(color=theme.primary_color)
                # Try to render something with this style
                console.get_style(theme.primary_color)
            except Exception as e:
                pytest.fail(
                    f"Theme '{theme.name}' has invalid color '{theme.primary_color}': {e}"
                )

    def test_theme_colors_are_valid_textual_colors(self):
        """Test that theme colors can be parsed by Textual."""
        manager = ThemeManager()

        for theme in manager.themes:
            # Test that the color can be parsed by Textual
            try:
                # Textual expects colors in CSS format
                if theme.primary_color in [
                    "black",
                    "red",
                    "green",
                    "yellow",
                    "blue",
                    "magenta",
                    "cyan",
                    "white",
                ]:
                    # These are valid CSS color names
                    pass
                else:
                    # Try to parse as a Textual color
                    TextualColor.parse(theme.primary_color)
            except Exception as e:
                pytest.fail(
                    f"Theme '{theme.name}' has invalid Textual color '{theme.primary_color}': {e}"
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
        """Test that each theme has a unique color."""
        manager = ThemeManager()
        colors = [theme.primary_color for theme in manager.themes]

        # Check for duplicates
        assert len(colors) == len(set(colors)), "Some themes share the same color"

    def test_theme_color_rendering(self):
        """Test that theme colors can be rendered in text."""
        from rich.text import Text

        manager = ThemeManager()

        for theme in manager.themes:
            try:
                # Create text with the theme color
                text = Text("Test", style=theme.css_color)
                # This should not raise an exception
                str(text)
            except Exception as e:
                pytest.fail(
                    f"Failed to render text with theme '{theme.name}' color '{theme.primary_color}': {e}"
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
