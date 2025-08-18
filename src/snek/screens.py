"""Screen implementations for the Snek game using Textual's Screen system."""

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.timer import Timer
from textual.widgets import Label, Static
from textual_pyfiglet import FigletWidget

from .config import GameConfig, default_config
from .constants import MIN_GAME_HEIGHT, MIN_GAME_WIDTH, SIDE_PANEL_WIDTH
from .game import Game
from .game_rules import Direction


class SplashScreen(Screen):
    """Splash screen with retro arcade vibes."""
    
    # Make sure the screen can receive focus and key events
    can_focus = True

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

    def on_mount(self) -> None:
        """Fade in the splash screen on load."""
        self.styles.animate("opacity", value=1.0, duration=1.0)

    async def on_key(self, event: events.Key) -> None:
        """Handle key presses on splash screen."""
        if event.key == "enter":
            game_screen = GameScreen()
            self.app.push_screen(game_screen)
        elif event.key.lower() == "q":
            self.app.exit()
        event.stop()


class GameScreen(Screen):
    """Main game screen containing the snake game and side panel."""
    
    # Make sure the screen can receive focus and key events
    can_focus = True

    def __init__(self, config: GameConfig = None) -> None:
        super().__init__()
        self.config = config or default_config
        self.game: Game | None = None
        self.view_widget: SnakeView | None = None
        self.stats_widget: SidePanel | None = None
        self.timer: Timer | None = None
        self.interval: float | None = None
        self.sidebar_visible: bool = True

    def compose(self) -> ComposeResult:
        """Compose the game screen."""
        # Initialize game with default size - will be resized on mount
        game_width, game_height = 20, 15

        self.game = Game(width=game_width, height=game_height, config=self.config)
        self.view_widget = SnakeView(self.game, self.config)
        self.stats_widget = SidePanel(self.game)

        yield Horizontal(self.view_widget, self.stats_widget, id="game-content")

    def on_mount(self) -> None:
        """Start the game timer when the screen mounts."""
        if self.game:
            # Always start the timer - game dimensions will be set by compose
            self.interval = self.config.initial_speed_interval
            self.timer = self.set_interval(self.interval, self.tick)

            # Set initial theme
            if hasattr(self.app, "theme") and self.game.world_path:
                self.app.theme = self.game.world_path.get_world(0).theme_name
        
        # Focus this screen to receive key events
        self.focus()

    def on_unmount(self) -> None:
        """Clean up timer when screen is unmounted."""
        if self.timer:
            self.timer.stop()
            self.timer = None

    def _calculate_game_dimensions(
        self, terminal_width: int, terminal_height: int
    ) -> tuple[int, int]:
        """Calculate game dimensions from terminal size."""
        sidebar_width = SIDE_PANEL_WIDTH if self.sidebar_visible else 0
        game_width = max(MIN_GAME_WIDTH, (terminal_width - sidebar_width) // 2)
        game_height = max(MIN_GAME_HEIGHT, terminal_height)
        return game_width, game_height

    def tick(self) -> None:
        """Game tick - advance game state."""
        if not self.game:
            return

        pre_length = len(self.game.snake)
        old_world = self.game.current_world

        self.game.step()

        # Update theme if world changed
        if self.game.current_world != old_world and hasattr(self.app, "theme"):
            self.app.theme = self.game.world_path.get_world(
                self.game.current_world
            ).theme_name
            if self.stats_widget:
                self.stats_widget.update_content()

        if self.game.game_over:
            # Stop the timer to prevent multiple game over modals
            if self.timer:
                self.timer.stop()
                self.timer = None
            self.app.push_screen(GameOverModal())
            return

        if len(self.game.snake) > pre_length:
            # Snake ate food; increase speed
            self.interval *= self.config.speed_increase_factor
            if self.timer:
                self.timer.stop()
            self.timer = self.set_interval(self.interval, self.tick)
            self.game.update_speed(self.interval)

        if self.view_widget:
            self.view_widget.refresh()
        if self.stats_widget:
            self.stats_widget.update_content()

    def action_pause(self) -> None:
        """Pause the game."""
        if self.game and not self.game.game_over:
            self.game.paused = True
            if self.timer:
                self.timer.stop()
            self.app.push_screen(PauseModal())

    def action_toggle_sidebar(self) -> None:
        """Toggle sidebar visibility."""
        if not self.stats_widget:
            return

        self.sidebar_visible = not self.sidebar_visible

        if self.sidebar_visible:
            self.stats_widget.styles.display = "block"
        else:
            self.stats_widget.styles.display = "none"

    async def on_key(self, event: events.Key) -> None:
        """Handle key presses for game controls."""
        if not self.game:
            return

        # Handle game controls
        if event.key in ("up", "down", "left", "right"):
            self.game.turn(Direction[event.key.upper()])
        elif event.key in ("w", "a", "s", "d"):
            direction_map = {"w": "UP", "s": "DOWN", "a": "LEFT", "d": "RIGHT"}
            self.game.turn(Direction[direction_map[event.key]])
        elif event.key == "p":
            self.action_pause()
        elif event.key == "space":
            self.action_toggle_sidebar()
        elif event.key == "q":
            self.action_quit()

        # Force a refresh after key press to show immediate response
        if self.view_widget:
            self.view_widget.refresh()
        if self.stats_widget:
            self.stats_widget.update_content()
        
        event.stop()

    def action_quit(self) -> None:
        """Quit to splash screen."""
        self.app.pop_screen()

    def resume_game(self) -> None:
        """Resume the game after pause."""
        if self.game and self.game.paused:
            self.game.paused = False
            if self.interval:
                self.timer = self.set_interval(self.interval, self.tick)


class PauseModal(ModalScreen):
    """Modal screen shown when game is paused."""

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

    async def on_key(self, event: events.Key) -> None:
        """Handle key presses in pause modal."""
        if event.key == "enter":
            # Resume the game
            for screen in self.app.screen_stack:
                if isinstance(screen, GameScreen):
                    screen.resume_game()
                    break
            self.dismiss()
        elif event.key.lower() == "q":
            # Quit to splash screen
            self.dismiss()
            self.app.pop_screen()
        event.stop()


class GameOverModal(ModalScreen):
    """Modal screen shown when snek dies."""
    
    # Make sure the modal can receive focus and key events
    can_focus = True

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
            yield Static("Press ENTER to restart or Q to quit", classes="death-prompt")

    def on_mount(self) -> None:
        """Ensure the modal gets focus when mounted."""
        self.focus()

    async def on_key(self, event: events.Key) -> None:
        """Handle key presses in game over modal."""
        if event.key == "enter":
            # Restart the game - pop current game screen and push new one
            self.app.pop_screen()  # Remove the GameScreen beneath this modal
            self.app.push_screen(GameScreen())  # Push new GameScreen
            self.dismiss()  # Remove this modal last
        elif event.key.lower() == "q":
            # Quit to splash screen - pop game screen and dismiss modal
            self.app.pop_screen()  # Remove the GameScreen beneath this modal
            self.dismiss()  # Remove this modal last
        event.stop()


class SnakeView(Static):
    """Renders the game as text."""

    def __init__(self, game: Game, config: GameConfig = None) -> None:
        super().__init__()
        self.game = game
        self.config = config or default_config

    def on_resize(self, event: events.Resize) -> None:
        """React to available space changes."""
        if self.game and self.size.width > 0 and self.size.height > 0:
            # Calculate grid size based on available space
            game_width = max(MIN_GAME_WIDTH, self.size.width // 2)
            game_height = max(MIN_GAME_HEIGHT, self.size.height)
            self.game.resize(game_width, game_height)
            self.refresh()

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

    def __init__(self, game: Game) -> None:
        super().__init__()
        self.game = game
        # Set width programmatically to have single source of truth
        self.styles.width = SIDE_PANEL_WIDTH
        self.styles.min_width = SIDE_PANEL_WIDTH

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
                    Label("Progress:", classes="stat-label"),
                    Label("", id="symbols-value", classes="stat-value"),
                    classes="stat-row",
                ),
                Horizontal(
                    Label("Total foods:", classes="stat-label"),
                    Label("", id="foods-value", classes="stat-value"),
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
        world_name = self.game.world_path.get_world_name(self.game.current_world)
        self.query_one("#world-value", Label).update(world_name)
        self.query_one("#symbols-value", Label).update(
            f"{self.game.symbols_in_current_world}/{self.game.config.symbols_per_world}"
        )
        self.query_one("#foods-value", Label).update(str(self.game.symbols_consumed))
        self.query_one("#speed-value", Label).update(
            f"{self.game.get_moves_per_second():.1f}/sec"
        )
