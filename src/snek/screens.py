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

from . import __version__
from .demo_ai import DemoAI
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
            yield Static(f"v{__version__}", classes="version-display")

    def on_mount(self) -> None:
        """Fade in the splash screen on load."""
        self.styles.animate("opacity", value=1.0, duration=1.0)

    def action_start_game(self) -> None:
        """Start the game."""
        game_screen = self.app.get_screen("game")
        game_screen.set_user_mode()
        self.app.push_screen("game")

    def action_start_demo(self) -> None:
        """Start the game in demo mode."""
        game_screen = self.app.get_screen("game")
        game_screen.set_demo_mode()
        self.app.push_screen("game")

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

    def __init__(self) -> None:
        super().__init__()
        self.timer: Timer | None = None
        self.interval: float = self.app.config.initial_speed_interval
        self.sidebar_visible: bool = True
        self.demo_ai: DemoAI | None = None

    def compose(self) -> ComposeResult:
        """Compose the game screen."""
        yield Horizontal(SnakeView(), SidePanel(), id="game-content")

    def on_mount(self) -> None:
        """Start the game timer and set initial theme when the screen mounts."""
        self.timer = self.set_interval(self.interval, self.tick)
        self.app.theme = self.app.game.world_path.get_world(0).theme_name

    def on_unmount(self) -> None:
        """Clean up timer when screen is unmounted."""
        if self.timer:
            self.timer.stop()

    def _restart_timer(self) -> None:
        """Helper to restart the game timer with current interval."""
        if self.timer:
            self.timer.stop()
        self.timer = self.set_interval(self.interval, self.tick)

    def _update_reactive_fields(self) -> None:
        """Update all reactive fields from game state."""
        self.foods_eaten = self.app.game.symbols_consumed
        self.speed = self.app.game.get_moves_per_second()
        self.world_index = self.app.game.current_world
        self.symbols_in_world = self.app.game.symbols_in_current_world

        side_panel = self.query_one(SidePanel)
        side_panel.foods_eaten = self.app.game.symbols_consumed
        side_panel.speed = self.app.game.get_moves_per_second()
        side_panel.world_index = self.app.game.current_world
        side_panel.symbols_in_world = self.app.game.symbols_in_current_world

    def tick(self) -> None:
        """Game tick - advance game state."""
        if self.demo_ai:
            # In demo mode, let the AI choose the direction
            ai_direction = self.demo_ai.get_next_direction()
            if ai_direction:
                self.app.game.turn(ai_direction)

        pre_length = len(self.app.game.snake)
        old_world = self.app.game.current_world
        self.app.game.step()

        if self.app.game.current_world != old_world:
            # World changed; update theme
            self.app.theme = self.app.game.world_path.get_world(
                self.app.game.current_world
            ).theme_name

        if self.app.game.game_over:
            # Stop the timer to prevent multiple game over modals
            if self.timer:
                self.timer.stop()
            self.app.push_screen("game_over")
            return

        if len(self.app.game.snake) > pre_length:
            # Snake ate food; increase speed
            self.interval *= self.app.config.speed_increase_factor
            self._restart_timer()
            self.app.game.update_speed(self.interval)

        self._update_reactive_fields()
        self.query_one(SnakeView).refresh()

    def action_pause(self) -> None:
        """Pause the game."""
        if not self.app.game.game_over:
            self.app.game.paused = True
            if self.timer:
                self.timer.pause()
            self.app.push_screen("pause")

    def action_toggle_sidebar(self) -> None:
        """Toggle sidebar visibility."""
        self.sidebar_visible = not self.sidebar_visible
        side_panel = self.query_one(SidePanel)
        side_panel.styles.display = "block" if self.sidebar_visible else "none"
        self.refresh(layout=True)

    def action_turn(self, dir_name: str) -> None:
        """Turn the snake in the specified direction."""
        if self.demo_ai:
            # Don't allow manual control in demo mode
            return

        self.app.game.turn(Direction[dir_name])
        # Force a refresh after key press to show immediate response
        self.query_one(SnakeView).refresh()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def resume_game(self) -> None:
        """Resume the game after pause."""
        if self.app.game.paused:
            self.app.game.paused = False
            if self.timer:
                self.timer.resume()

    def restart_game(self) -> None:
        """Restart the game."""
        self.app.game.reset()
        if self.demo_ai:
            # Recreate AI for fresh game
            self.demo_ai = DemoAI(self.app.game)
        self.interval = self.app.config.initial_speed_interval
        self._restart_timer()
        self._update_reactive_fields()
        # Update theme to initial world before refreshing view
        self.app.theme = self.app.game.world_path.get_world(0).theme_name
        self.query_one(SnakeView).refresh()

    def set_demo_mode(self) -> None:
        """Enable demo mode with AI control."""
        if not self.demo_ai:
            self.demo_ai = DemoAI(self.app.game)

    def set_user_mode(self) -> None:
        """Disable demo mode - user controls."""
        self.demo_ai = None


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
        game_screen = self.app.get_screen("game")
        game_screen.resume_game()
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()


class GameOverModal(ModalScreen):
    """Modal screen shown when snek dies."""

    BINDINGS = [
        ("space", "restart", "Restart"),
        ("enter", "menu", "Main Menu"),
        ("q", "quit", "Quit"),
    ]

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
                "Press SPACE to restart, ENTER for main menu, or Q to quit",
                classes="death-prompt",
            )

    def action_restart(self) -> None:
        """Restart the game in the same mode (user/demo)."""
        game_screen = self.app.get_screen("game")
        game_screen.restart_game()
        self.app.pop_screen()
        self.app.pop_screen()

    def action_menu(self) -> None:
        """Return to the main menu (splash screen)."""
        self.app.pop_screen()
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()


class SnakeView(Static):
    """Renders the game as text."""

    def on_resize(self, event: events.Resize) -> None:
        """React to available space changes."""
        if self.app.game and self.size.width > 0 and self.size.height > 0:
            # Calculate grid size based on available space
            game_width = max(self.app.config.min_game_width, self.size.width // 2)
            game_height = max(self.app.config.min_game_height, self.size.height)
            self.app.app.game.resize(game_width, game_height)
            self.refresh()

    def render(self) -> Text:
        """Render the game grid using solid block symbols for the snake."""
        width, height = self.app.game.width, self.app.game.height
        empty_cell = self.app.config.empty_cell
        food_emoji = self.app.game.food_emoji
        snake_block = self.app.game.config.snake_block
        food_pos = self.app.game.food

        snake_positions = set(self.app.game.snake)
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


class StatsRow(Static):
    """A component for displaying a statistics row with label and value."""

    def __init__(self, label: str, value_id: str) -> None:
        super().__init__()
        self.label = label
        self.value_id = value_id

    def compose(self) -> ComposeResult:
        """Compose the stats row."""
        yield Horizontal(
            Label(f"{self.label}:", classes="stat-label"),
            Label("", id=self.value_id, classes="stat-value"),
            classes="stat-row",
        )


class SidePanel(Static):
    """Panel showing game statistics."""

    foods_eaten = reactive(0)
    speed = reactive(0.0)
    world_index = reactive(0)
    symbols_in_world = reactive(0)

    def __init__(self) -> None:
        super().__init__()
        self.styles.width = self.app.config.side_panel_width
        self.styles.min_width = self.app.config.side_panel_width

    def compose(self) -> ComposeResult:
        """Compose the side panel with FigletWidget at bottom."""
        yield Vertical(
            Vertical(
                StatsRow("World", "world-value"),
                StatsRow("Progress", "symbols-value"),
                StatsRow("Total foods", "foods-value"),
                StatsRow("Speed", "speed-value"),
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

    def watch_foods_eaten(self, value: int) -> None:
        """React to foods eaten changes."""
        self.query_one("#foods-value", Label).update(str(value))

    def watch_speed(self, value: float) -> None:
        """React to speed changes."""
        self.query_one("#speed-value", Label).update(f"{value:.1f}/sec")

    def watch_world_index(self, value: int) -> None:
        """React to world index changes."""
        world_name = self.app.game.world_path.get_world_name(value)
        self.query_one("#world-value", Label).update(world_name)

    def watch_symbols_in_world(self, value: int) -> None:
        """React to symbols in current world changes."""
        self.query_one("#symbols-value", Label).update(
            f"{value}/{self.app.config.symbols_per_world}"
        )
