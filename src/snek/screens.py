"""Screen implementations for the Snek game using Textual's Screen system."""

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.timer import Timer
from textual.widgets import Label, Static
from textual_pyfiglet import FigletWidget

from .config import GameConfig, default_config
from .demo_ai import DemoAI
from .game import Game
from .game_rules import Direction


class SplashScreen(Screen):
    """Splash screen for Snek."""

    BINDINGS = [
        ("space", "start_game", "Start Game"),
        ("d", "start_demo", "Start Demo"),
        ("q", "quit", "Quit"),
    ]

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
            yield Static(
                "Press SPACE to start or D for demo mode.", classes="splash-prompt"
            )
            yield Static(
                "Use arrow or WASD keys to move, Space to pause, Q to quit.",
                classes="splash-prompt",
            )

    def on_mount(self) -> None:
        """Fade in the splash screen on load."""
        self.styles.animate("opacity", value=1.0, duration=1.0)

    def action_start_game(self) -> None:
        """Start the game."""
        game_screen = GameScreen()
        self.app.push_screen(game_screen)

    def action_start_demo(self) -> None:
        """Start the game in demo mode."""
        game_screen = GameScreen(demo_mode=True)
        self.app.push_screen(game_screen)

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()


class GameScreen(Screen):
    """Main game screen containing the snake game and side panel."""

    BINDINGS = [
        ("up", "turn('UP')", "Up"),
        ("down", "turn('DOWN')", "Down"),
        ("left", "turn('LEFT')", "Left"),
        ("right", "turn('RIGHT')", "Right"),
        ("w", "turn('UP')", None),
        ("s", "turn('DOWN')", None),
        ("a", "turn('LEFT')", None),
        ("d", "turn('RIGHT')", None),
        ("space", "pause", "Pause"),
        ("enter", "toggle_sidebar", "Toggle Sidebar"),
        ("q", "quit", "Quit"),
    ]

    foods_eaten = reactive(0)
    speed = reactive(0.0)
    world_index = reactive(0)
    symbols_in_world = reactive(0)

    def __init__(self, config: GameConfig = None, demo_mode: bool = False) -> None:
        super().__init__()
        self.config = config or default_config
        self.demo_mode = demo_mode
        # Initialize game with default size - will be resized on mount
        self.game: Game = Game(width=20, height=15, config=self.config)
        self.demo_ai: DemoAI | None = None
        if self.demo_mode:
            self.demo_ai = DemoAI(self.game)
        self.view_widget: SnakeView | None = None
        self.stats_widget: SidePanel | None = None
        self.timer: Timer | None = None
        self.interval: float | None = None
        self.sidebar_visible: bool = True

    def compose(self) -> ComposeResult:
        """Compose the game screen."""
        self.view_widget = SnakeView(self.game)
        self.stats_widget = SidePanel(self.game)

        yield Horizontal(self.view_widget, self.stats_widget, id="game-content")

    def on_mount(self) -> None:
        """Start the game timer when the screen mounts."""
        # Always start the timer - game dimensions will be set by compose
        # Use faster speed for demo mode for better visual experience
        if self.demo_mode:
            self.interval = self.config.initial_speed_interval * 0.6  # 40% faster
        else:
            self.interval = self.config.initial_speed_interval
        self._restart_timer()

        # Set initial theme
        if hasattr(self.app, "theme"):
            self.app.theme = self.game.world_path.get_world(0).theme_name

    def on_unmount(self) -> None:
        """Clean up timer when screen is unmounted."""
        if self.timer:
            self.timer.stop()
            self.timer = None

    def _restart_timer(self) -> None:
        """Helper to safely restart the game timer."""
        if self.timer:
            self.timer.stop()
        self.timer = self.set_interval(self.interval, self.tick)

    def tick(self) -> None:
        """Game tick - advance game state."""
        # In demo mode, let the AI choose the direction
        if self.demo_mode and self.demo_ai:
            ai_direction = self.demo_ai.get_next_direction()
            if ai_direction:
                self.game.turn(ai_direction)

        pre_length = len(self.game.snake)
        old_world = self.game.current_world
        self.game.step()

        # Update theme if world changed
        if self.game.current_world != old_world and hasattr(self.app, "theme"):
            self.app.theme = self.game.world_path.get_world(
                self.game.current_world
            ).theme_name

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
            self._restart_timer()
            self.game.update_speed(self.interval)

        # Update reactive fields
        self.foods_eaten = self.game.symbols_consumed
        self.speed = self.game.get_moves_per_second()
        self.world_index = self.game.current_world
        self.symbols_in_world = self.game.symbols_in_current_world

        # Update stats-panel reactive fields
        if self.stats_widget:
            self.stats_widget.foods_eaten = self.game.symbols_consumed
            self.stats_widget.speed = self.game.get_moves_per_second()
            self.stats_widget.world_index = self.game.current_world
            self.stats_widget.symbols_in_world = self.game.symbols_in_current_world

        if self.view_widget:
            self.view_widget.refresh()

    def action_pause(self) -> None:
        """Pause the game."""
        if not self.game.game_over:
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
        self.refresh(layout=True)

    def action_turn(self, dir_name: str) -> None:
        """Turn the snake in the specified direction."""
        # Don't allow manual control in demo mode
        if self.demo_mode:
            return
        self.game.turn(Direction[dir_name])
        if self.view_widget:
            # Force a refresh after key press to show immediate response
            self.view_widget.refresh()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def resume_game(self) -> None:
        """Resume the game after pause."""
        if self.game.paused:
            self.game.paused = False
            if self.interval:
                self._restart_timer()

    def restart_game(self) -> None:
        """Restart the game."""
        self.game.reset()
        if self.demo_mode and self.demo_ai:
            self.demo_ai = DemoAI(self.game)  # Recreate AI for fresh game
        self.interval = self.config.initial_speed_interval
        self._restart_timer()

        # Update reactive fields
        self.foods_eaten = self.game.symbols_consumed
        self.speed = self.game.get_moves_per_second()
        self.world_index = self.game.current_world
        self.symbols_in_world = self.game.symbols_in_current_world

        # Update stats-panel
        if self.stats_widget:
            self.stats_widget.foods_eaten = self.game.symbols_consumed
            self.stats_widget.speed = self.game.get_moves_per_second()
            self.stats_widget.world_index = self.game.current_world
            self.stats_widget.symbols_in_world = self.game.symbols_in_current_world

        if self.view_widget:
            self.view_widget.refresh()

        if hasattr(self.app, "theme"):
            # Update theme to initial world
            self.app.theme = self.game.world_path.get_world(0).theme_name


class PauseModal(ModalScreen):
    """Modal screen shown when game is paused."""

    BINDINGS = [
        ("space", "resume", "Resume"),
        ("q", "quit", "Quit"),
    ]

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
            yield Static("Press SPACE to continue", id="pause-prompt")
            yield Static("KEYBOARD CONTROLS", id="controls-header")
            with Vertical(id="controls-container"):
                yield Static("Arrows / WASD: Move the snek")
                yield Static("        Space: Pause the game")
                yield Static("        Enter: Toggle sidebar")
                yield Static("            Q: Quit the game")

    def action_resume(self) -> None:
        """Resume the game."""
        for screen in self.app.screen_stack:
            if isinstance(screen, GameScreen):
                screen.resume_game()
                break
        self.dismiss()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()


class GameOverModal(ModalScreen):
    """Modal screen shown when snek dies."""

    BINDINGS = [
        ("space", "restart", "Restart"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the death screen with FigletWidget."""
        # Check if we're in demo mode to show appropriate prompt
        demo_mode = False
        for screen in self.app.screen_stack:
            if isinstance(screen, GameScreen):
                demo_mode = screen.demo_mode
                break

        prompt_text = (
            "Press SPACE to return to menu or Q to quit"
            if demo_mode
            else "Press SPACE to restart or Q to quit"
        )

        with Vertical(id="death-container"):
            yield FigletWidget(
                "GAME OVER",
                font="doom",
                id="death-title",
                colors=["$primary"],
                classes="title-text",
            )
            yield Static("💀 SNEK DIED! 💀", classes="death-message")
            yield Static(prompt_text, classes="death-prompt")

    def action_restart(self) -> None:
        """Restart the game or return to splash if in demo mode."""
        for screen in self.app.screen_stack:
            if isinstance(screen, GameScreen):
                if screen.demo_mode:
                    # In demo mode, return to splash screen instead of restarting
                    self.app.pop_screen()  # Remove GameOverModal
                    self.app.pop_screen()  # Remove GameScreen
                    return
                else:
                    screen.restart_game()
                    break
        self.dismiss()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()


class SnakeView(Static):
    """Renders the game as text."""

    def __init__(self, game: Game) -> None:
        super().__init__()
        self.game = game

    def on_resize(self, event: events.Resize) -> None:
        """React to available space changes."""
        if self.game and self.size.width > 0 and self.size.height > 0:
            # Calculate grid size based on available space
            game_width = max(self.game.config.min_game_width, self.size.width // 2)
            game_height = max(self.game.config.min_game_height, self.size.height)
            self.game.resize(game_width, game_height)
            self.refresh()

    def render(self) -> Text:
        """Render the game grid using solid block symbols for the snake."""
        width, height = self.game.width, self.game.height
        empty_cell = self.game.config.empty_cell
        food_emoji = self.game.food_emoji
        snake_block = self.game.config.snake_block
        food_pos = self.game.food

        snake_positions = set(self.game.snake)
        rows = []
        for y in range(height):
            row_parts = []
            for x in range(width):
                pos = (x, y)
                if pos in snake_positions:
                    row_parts.append(snake_block)
                elif pos == food_pos:
                    row_parts.append(f"{food_emoji} ")
                else:
                    row_parts.append(empty_cell)
            rows.append("".join(row_parts))
        return Text("\n".join(rows))


class SidePanel(Static):
    """Panel showing game statistics."""

    foods_eaten = reactive(0)
    speed = reactive(0.0)
    world_index = reactive(0)
    symbols_in_world = reactive(0)

    def __init__(self, game: Game) -> None:
        super().__init__()
        self.game = game
        self.styles.width = self.game.config.side_panel_width
        self.styles.min_width = self.game.config.side_panel_width

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

    def watch_foods_eaten(self, value: int) -> None:
        """React to foods eaten changes."""
        self.query_one("#foods-value", Label).update(str(value))

    def watch_speed(self, value: float) -> None:
        """React to speed changes."""
        self.query_one("#speed-value", Label).update(f"{value:.1f}/sec")

    def watch_world_index(self, value: int) -> None:
        """React to world index changes."""
        world_name = self.game.world_path.get_world_name(value)
        self.query_one("#world-value", Label).update(world_name)

    def watch_symbols_in_world(self, value: int) -> None:
        """React to symbols in current world changes."""
        self.query_one("#symbols-value", Label).update(
            f"{value}/{self.game.config.symbols_per_world}"
        )
