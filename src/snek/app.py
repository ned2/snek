"""Main Textual application for the Snek game."""

from textual.app import App

from .config import GameConfig, default_config
from .screens import SplashScreen
from .themes import THEME_MAP


class SnakeApp(App):
    """Main Snek application using Textual's Screen system."""

    CSS_PATH = "styles.css"

    def __init__(self, config: GameConfig = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config or default_config

    def on_load(self) -> None:
        """Register all themes when the app loads."""
        for theme in THEME_MAP.values():
            self.register_theme(theme)
        self.theme = "snek-classic"

    def on_mount(self) -> None:
        """Start with the splash screen."""
        self.push_screen(SplashScreen())
