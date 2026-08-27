"""Main Textual application for the Snek game."""

from typing import Any

from textual.app import App

from .config import GameConfig, default_config
from .demo import DEFAULT_STRATEGY
from .game import Game
from .screens import GameScreen, PauseModal, SplashScreen
from .themes import THEME_MAP


class SnakeApp(App[None]):
    """Main Snek application using Textual's Screen system."""

    CSS_PATH = "styles.css"

    SCREENS = {
        "splash": SplashScreen,
        "game": GameScreen,
        "pause": PauseModal,
    }
    # `GameOverModal` is intentionally NOT a registered (singleton) screen: it is
    # pushed as a fresh instance each game-over (see `GameScreen.tick`) so its
    # banner and final score always reflect the game that just ended.

    def __init__(
        self,
        config: GameConfig | None = None,
        demo_strategy: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        # GameConfig is immutable, so the app and model safely share one value.
        self.config: GameConfig = default_config if config is None else config
        # Which demo strategy to construct (set by the `--demo-strategy` CLI flag);
        # the game screen reads this when entering demo mode. Falls back to default.
        self.demo_strategy = demo_strategy or DEFAULT_STRATEGY
        self.game = Game(config=self.config)

    def on_load(self) -> None:
        """Register all themes when the app loads."""
        for theme in THEME_MAP.values():
            self.register_theme(theme)
        self.theme = "snek-classic"

    def on_mount(self) -> None:
        """Start with the splash screen."""
        self.push_screen("splash")
