"""Theme management for the Snek game."""

from textual.theme import Theme


class ThemeManager:
    """Manages game themes and level-based theme selection."""

    def __init__(self):
        self.themes = self._create_default_themes()
        self.current_theme_index = 0

    def _create_default_themes(self) -> list[Theme]:
        """Create the default theme progression."""
        return [
            Theme(
                name="snek-classic",
                primary="#00ff00",  # Bright green
                secondary="#00cc00",
                accent="#ffff00",
                foreground="#ffffff",
                background="#000000",
                success="#00ff00",
                warning="#ffff00",
                error="#ff0000",
                surface="#1a1a1a",
                panel="#2a2a2a",
                dark=True,
            ),
            Theme(
                name="snek-ocean",
                primary="#00ffff",  # Cyan
                secondary="#0099cc",
                accent="#00ff99",
                foreground="#e0f7fa",
                background="#001f3f",
                success="#00ff99",
                warning="#ffcc00",
                error="#ff6b6b",
                surface="#003366",
                panel="#004080",
                dark=True,
            ),
            Theme(
                name="snek-sunset",
                primary="#ffff00",  # Yellow
                secondary="#ff9900",
                accent="#ff6600",
                foreground="#fff8dc",
                background="#1a0f00",
                success="#90ee90",
                warning="#ffa500",
                error="#ff4500",
                surface="#2a1f00",
                panel="#3a2f00",
                dark=True,
            ),
            Theme(
                name="snek-royal",
                primary="#ff00ff",  # Magenta
                secondary="#cc00cc",
                accent="#ff66ff",
                foreground="#ffe0ff",
                background="#1a001a",
                success="#90ee90",
                warning="#ffcc00",
                error="#ff6666",
                surface="#330033",
                panel="#4d004d",
                dark=True,
            ),
            Theme(
                name="snek-cherry",
                primary="#ff0000",  # Red
                secondary="#cc0000",
                accent="#ff6666",
                foreground="#ffe0e0",
                background="#1a0000",
                success="#90ee90",
                warning="#ffcc00",
                error="#ff0000",
                surface="#330000",
                panel="#4d0000",
                dark=True,
            ),
        ]

    def get_theme_for_level(self, level: int) -> Theme:
        """Get the theme for a given level, cycling through themes as level increases."""
        theme_index = (level - 1) % len(self.themes)
        return self.themes[theme_index]

    def get_theme_name_for_level(self, level: int) -> str:
        """Get the theme name for a given level."""
        return self.get_theme_for_level(level).name

    def get_current_theme(self) -> Theme:
        """Get the current active theme."""
        return self.themes[self.current_theme_index]

    def set_level(self, level: int) -> Theme:
        """Set theme based on level and return it."""
        self.current_theme_index = (level - 1) % len(self.themes)
        return self.get_current_theme()

    def get_all_themes(self) -> list[Theme]:
        """Get all available themes."""
        return self.themes
