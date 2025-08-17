from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Label, Static
from textual_pyfiglet import FigletWidget

from .config import GameConfig, default_config
from .constants import (
    GameState,
    MIN_GAME_HEIGHT,
    MIN_GAME_WIDTH,
    SIDE_PANEL_WIDTH,
)
from .game import Game
from .game_rules import Direction
from .state_manager import StateManager
from .themes import ThemeManager


class SplashView(Vertical):
    can_focus = True
    """Splash screen with retro arcade vibes."""

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.theme_manager = theme_manager

    def compose(self) -> ComposeResult:
        """Compose the splash screen with FigletWidget."""
        with Vertical(id="splash-container"):
            yield FigletWidget(
                "SNEK",
                font="doh",
                id="splash-title",
                classes="title-text",
                colors=["$primary", "$panel"],
                animate=True,
            )
            yield Static("Press ENTER to start", classes="splash-prompt")
            yield Static(
                "Use arrow keys to move, P to pause, Q to quit",
                classes="splash-prompt",
            )

    async def on_key(self, event: events.Key) -> None:
        """Start game on Enter key press, or quit on Q."""
        if event.key.lower() == "q":
            await self.app.action_quit()
        elif event.key == "enter":
            self.app.start_game()
        event.stop()


class DeathView(Vertical):
    can_focus = True
    """Splash screen shown when snek dies."""

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.theme_manager = theme_manager

    def compose(self) -> ComposeResult:
        """Compose the death screen with FigletWidget."""
        with Vertical(id="death-container"):
            yield FigletWidget(
                "GAME OVER",
                font="doom",
                id="death-title",
                colors=["$primary"],
                classes="title-text",
            )
            yield Static("💀 SNEK DIED! 💀", classes="death-message")
            yield Static(
                "Press ENTER to restart or Q to quit", classes="death-prompt"
            )


class PauseView(Vertical):
    can_focus = True
    """Splash screen shown when game is paused."""

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.theme_manager = theme_manager

    def compose(self) -> ComposeResult:
        """Compose the pause screen with FigletWidget."""
        with Vertical(id="pause-container"):
            yield FigletWidget(
                "PAUSED",
                font="doom",
                id="pause-title",
                colors=["$primary"],
                classes="title-text",
            )
            yield Static("Press ENTER to continue", classes="pause-prompt")


class SnakeView(Static):
    """Renders the game as text."""

    def __init__(
        self, game: Game, theme_manager: ThemeManager, config: GameConfig = None
    ) -> None:
        super().__init__()
        self.game = game
        self.theme_manager = theme_manager
        self.config = config or default_config

    def render(self) -> Text:
        """Render the game grid using solid block symbols for the snake."""
        width, height = self.game.width, self.game.height
        snake = self.game.snake
        text = Text()

        for y in range(height):
            for x in range(width):
                if (x, y) in snake:
                    # Use markup for theming - will be styled by CSS
                    text.append(self.config.snake_block)
                elif (x, y) == self.game.food:
                    text.append(f"{self.game.food_emoji} ")
                else:
                    text.append(self.config.empty_cell)
            if y < height - 1:
                # Don't add newline after last row
                text.append("\n")

        if self.game.game_over:
            text.append("\n\n GAME OVER! Press R to restart.")

        return text


class SidePanel(Static):
    """Panel showing game statistics."""

    def __init__(self, game: Game, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.game = game
        self.theme_manager = theme_manager

    def compose(self) -> ComposeResult:
        """Compose the side panel with FigletWidget at bottom."""
        yield Vertical(
            Vertical(
                Horizontal(
                    Label("World:", classes="stat-label"),
                    Label("", id="world-value", classes="stat-value"),
                    classes="stat-row",
                ),
                Horizontal(
                    Label("Symbols:", classes="stat-label"),
                    Label("", id="symbols-value", classes="stat-value"),
                    classes="stat-row",
                ),
                Horizontal(
                    Label("Speed:", classes="stat-label"),
                    Label("", id="speed-value", classes="stat-value"),
                    classes="stat-row",
                ),
                id="stats-content",
            ),
            FigletWidget(
                "SNEK",
                font="small",
                id="panel-title",
                colors=["$primary"],
            ),
            id="side-panel-container",
        )

    def on_mount(self) -> None:
        """Update content when mounted."""
        self.update_content()

    def update_content(self) -> None:
        """Update the stats content."""
        world_name = self.game.world_path.get_world_name(self.game.level)
        self.query_one("#world-value", Label).update(world_name)
        self.query_one("#symbols-value", Label).update(str(self.game.symbols_consumed))
        self.query_one("#speed-value", Label).update(
            f"{self.game.get_moves_per_second():.1f}/sec"
        )


class SnakeApp(App):
    def __init__(
        self, config: GameConfig = None, css_path: str = "styles.css", **kwargs
    ) -> None:
        self.CSS_PATH = css_path
        super().__init__(**kwargs)
        self.config = config or default_config
        self.theme_manager = ThemeManager()
        self.state_manager = StateManager()
        self.splash_view: SplashView | None = None
        self.game: Game | None = None
        self.view_widget: SnakeView | None = None
        self.stats_widget: SidePanel | None = None
        self.game_container: Horizontal | None = None
        self.timer: Timer | None = None
        self.interval: float | None = None
        self.death_view: DeathView | None = None
        self.pause_view: PauseView | None = None

        self._register_state_callbacks()

    def on_mount(self) -> None:
        """Register themes when the app mounts."""
        for theme in self.theme_manager.get_all_themes():
            self.register_theme(theme)
        self.theme = self.theme_manager.get_theme_name_for_level(1)
        # fade the splash screen in on load
        self.splash_view.styles.animate("opacity", value=1.0, duration=1.0)

    def _register_state_callbacks(self) -> None:
        """Register callbacks for state transitions."""
        self.state_manager.register_callback(GameState.PLAYING, self._on_playing_state)
        self.state_manager.register_callback(GameState.PAUSED, self._on_paused_state)
        self.state_manager.register_callback(
            GameState.GAME_OVER, self._on_game_over_state
        )

    def _on_playing_state(self) -> None:
        """Handle transition to playing state."""
        pass

    def _on_paused_state(self) -> None:
        """Handle transition to paused state."""
        pass

    def _on_game_over_state(self) -> None:
        """Handle transition to game over state."""
        pass

    def compose(self) -> ComposeResult:
        if self.state_manager.is_state(GameState.SPLASH):
            self.splash_view = SplashView(self.theme_manager)
            yield self.splash_view
        else:
            self.view_widget = SnakeView(self.game, self.theme_manager)
            yield Horizontal(self.view_widget, SidePanel(self.game, self.theme_manager))

    def _clear_all_widgets(self) -> None:
        """Clear all game-related widgets."""
        if self.splash_view:
            self.splash_view.remove()
            self.splash_view = None
        if self.death_view:
            self.death_view.remove()
            self.death_view = None
        if self.pause_view:
            self.pause_view.remove()
            self.pause_view = None
        if self.game_container:
            self.game_container.remove()
            self.game_container = None
        self.view_widget = None
        self.stats_widget = None

    def _calculate_game_dimensions(
        self, terminal_width: int, terminal_height: int
    ) -> tuple[int, int]:
        """Calculate game dimensions from terminal size."""
        game_width = max(MIN_GAME_WIDTH, (terminal_width - SIDE_PANEL_WIDTH) // 2)
        game_height = max(MIN_GAME_HEIGHT, terminal_height)
        return game_width, game_height

    def start_game(self) -> None:
        """Transition from splash screen to game."""
        self.state_manager.transition_to(GameState.PLAYING)

        self._clear_all_widgets()
        width, height = self.size
        game_width, game_height = self._calculate_game_dimensions(width, height)

        self.game = Game(width=game_width, height=game_height, config=self.config)
        self.view_widget = SnakeView(self.game, self.theme_manager, self.config)
        self.stats_widget = SidePanel(self.game, self.theme_manager)

        # Create layout: game and stats side by side
        self.game_container = Horizontal(
            self.view_widget, self.stats_widget, id="game-content"
        )

        self.mount(self.game_container)
        self.interval = self.config.initial_speed_interval
        self.timer = self.set_interval(self.interval, self.tick)
        self._timer_started = True

    def tick(self) -> None:
        pre_length = len(self.game.snake)
        old_level = self.game.level

        self.game.step()

        # Update theme if level changed
        if self.game.level != old_level:
            self.theme_manager.set_level(self.game.level)
            self.theme = self.theme_manager.get_theme_name_for_level(self.game.level)
            self.stats_widget.update_content()

        if self.game.game_over:
            self.show_death()
            return

        if len(self.game.snake) > pre_length:
            # Snake ate food; increase speed
            self.interval *= self.config.speed_increase_factor
            if self.timer:
                self.timer.stop()
            self.timer = self.set_interval(self.interval, self.tick)
            self.game.update_speed(self.interval)

        self.view_widget.refresh()
        self.stats_widget.update_content()

    def show_death(self) -> None:
        """Show death splash and wait for restart."""
        self.state_manager.transition_to(GameState.GAME_OVER)

        if self.timer:
            self.timer.stop()
            self.timer = None

        self._clear_all_widgets()
        self.death_view = DeathView(self.theme_manager)
        self.mount(self.death_view)
        self.death_view.focus()

    def pause_game(self) -> None:
        """Pause the game and show pause screen."""
        if not self.game or self.game.game_over or self.game.paused:
            return

        self.game.paused = True
        self.state_manager.transition_to(GameState.PAUSED)

        if self.timer:
            self.timer.stop()

        # Clear game widgets but keep references for unpausing
        if self.game_container:
            self.game_container.remove()

        self.pause_view = PauseView(self.theme_manager)
        self.mount(self.pause_view)
        self.pause_view.focus()

    def unpause_game(self) -> None:
        """Unpause the game and restore game view."""
        if not self.game or not self.game.paused:
            return

        self.game.paused = False
        self.state_manager.transition_to(GameState.PLAYING)

        if self.pause_view:
            self.pause_view.remove()
            self.pause_view = None

        # Recreate game widgets and game layout and mount game container
        self.view_widget = SnakeView(self.game, self.theme_manager, self.config)
        self.stats_widget = SidePanel(self.game, self.theme_manager)
        self.game_container = Horizontal(
            self.view_widget, self.stats_widget, id="game-content"
        )
        self.mount(self.game_container)
        self.timer = self.set_interval(self.interval, self.tick)

    async def on_key(self, event: events.Key) -> None:
        # Handle pause screen
        if self.game and self.game.paused and self.pause_view:
            if event.key == "enter":
                self.unpause_game()
            elif event.key.lower() == "q":
                await self.action_quit()
            return

        if self.state_manager.is_state(GameState.SPLASH):
            # Enter starts from splash screen
            if event.key == "enter":
                self.start_game()
            elif event.key.lower() == "q":
                await self.action_quit()
            return

        if self.state_manager.is_state(GameState.GAME_OVER):
            # Enter restarts, Q quits
            if event.key == "enter":
                self.start_game()
            elif event.key.lower() == "q":
                await self.action_quit()
            return

        # Handle game controls
        key = event.key.lower()
        if event.key in ("up", "down", "left", "right"):
            self.game.turn(Direction[event.key.upper()])
        elif key in ("w", "a", "s", "d"):
            direction_map = {"w": "UP", "s": "DOWN", "a": "LEFT", "d": "RIGHT"}
            self.game.turn(Direction[direction_map[key]])
        elif key == "p":
            self.pause_game()
        elif key == "q":
            await self.action_quit()

    async def on_ready(self) -> None:
        """Once the app is up, give focus to the splash screen so on_key fires."""
        if self.state_manager.is_state(GameState.SPLASH) and self.splash_view:
            self.splash_view.focus()

    async def on_resize(self, event: events.Resize) -> None:
        """Handle terminal resize by updating grid and scaling snake."""
        if self.game and self.view_widget:
            width, height = self.size
            game_width, game_height = self._calculate_game_dimensions(width, height)
            self.game.resize(game_width, game_height)
            self.view_widget.refresh()
            self.stats_widget.update_content()
