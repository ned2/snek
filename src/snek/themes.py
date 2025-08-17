"""Theme management for the Snek game."""

from dataclasses import dataclass

from .colors import get_valid_color


@dataclass
class Theme:
    """Represents a color theme for the game."""

    name: str
    primary_color: str

    def __post_init__(self):
        """Validate and normalize color on creation."""
        self.primary_color = get_valid_color(self.primary_color)

    @property
    def css_color(self) -> str:
        """Get CSS color string for this theme."""
        return self.primary_color


class ThemeManager:
    """Manages game themes and level-based theme selection."""

    def __init__(self):
        self.themes = self._create_default_themes()
        self.current_theme_index = 0

    def _create_default_themes(self) -> list[Theme]:
        """Create the default theme progression."""
        return [
            Theme(name="Classic", primary_color="green"),
            Theme(name="Ocean", primary_color="cyan"),
            Theme(name="Sunset", primary_color="yellow"),
            Theme(name="Royal", primary_color="magenta"),
            Theme(name="Cherry", primary_color="red"),
        ]

    def get_theme_for_level(self, level: int) -> Theme:
        """Get the theme for a given level, cycling through themes as level increases"""
        theme_index = (level - 1) % len(self.themes)
        return self.themes[theme_index]

    def get_current_theme(self) -> Theme:
        """Get the current active theme."""
        return self.themes[self.current_theme_index]

    def set_level(self, level: int) -> Theme:
        """Set theme based on level and return it."""
        self.current_theme_index = (level - 1) % len(self.themes)
        return self.get_current_theme()
