"""Main Textual application for the Snek game."""

from textual.app import App, ComposeResult

from .config import GameConfig, default_config
from .screens import SplashScreen
from .themes import THEME_MAP


class SnakeApp(App):
    """Main Snek application using Textual's Screen system."""

    def __init__(
        self, config: GameConfig = None, css_path: str = "styles.css", **kwargs
    ) -> None:
        self.CSS_PATH = css_path
        super().__init__(**kwargs)
        self.config = config or default_config

    def on_mount(self) -> None:
        """Register themes when the app mounts."""
        for theme in THEME_MAP.values():
            self.register_theme(theme)
        # Set initial theme to first world's theme
        self.theme = "snek-classic"
        # Start with the splash screen
        self.push_screen(SplashScreen())

    def compose(self) -> ComposeResult:
        """Compose the main app - screens handle their own composition."""
        # Empty compose - screens handle everything
        return []

    async def on_ready(self) -> None:
        """App is ready - nothing special needed as screens handle focus."""
        pass
