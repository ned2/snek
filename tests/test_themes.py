"""Tests for theme management."""

from snek.themes import LCD_BOARD_STYLE, LCD_DARK, LCD_LIGHT, THEME_MAP
from snek.worlds import WorldPath


class TestThemes:
    """Test theme functionality."""

    def test_all_themes_exist(self):
        """Test that all required themes exist in THEME_MAP."""
        expected_themes = [
            "snek-classic",
            "snek-ocean",
            "snek-sunset",
            "snek-royal",
            "snek-cherry",
        ]

        for theme_name in expected_themes:
            assert theme_name in THEME_MAP
            assert THEME_MAP[theme_name] is not None

    def test_theme_properties(self):
        """Test that themes have required properties."""
        for theme_name, theme in THEME_MAP.items():
            assert theme.name == theme_name
            assert theme.primary is not None
            assert theme.secondary is not None
            assert theme.background is not None
            assert theme.foreground is not None
            # Every theme is a world's, and dark; the LCD board is not a theme.
            assert theme.dark

    def test_world_theme_mapping(self):
        """Test that each world has a valid theme."""
        world_path = WorldPath()

        for i in range(len(world_path.worlds)):
            world = world_path.get_world(i)
            assert hasattr(world, "theme_name")
            assert world.theme_name in THEME_MAP

            # Test theme property
            assert world.theme == THEME_MAP[world.theme_name]
            assert world.theme.name == world.theme_name

    def test_theme_colors_unique(self):
        """Test that each theme has unique primary colors."""
        primary_colors = [theme.primary for theme in THEME_MAP.values()]
        assert len(primary_colors) == len(set(primary_colors))

    def test_lcd_board_is_two_tone(self):
        """The LCD board is dark pixels on a green-grey light."""
        assert (LCD_LIGHT, LCD_DARK) == ("#c7f0d8", "#43523d")
        assert LCD_BOARD_STYLE.color is not None
        assert LCD_BOARD_STYLE.bgcolor is not None
        assert LCD_BOARD_STYLE.color.name == LCD_DARK
        assert LCD_BOARD_STYLE.bgcolor.name == LCD_LIGHT
