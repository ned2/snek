"""Screen implementations for the Snek game using Textual's Screen system."""

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.timer import Timer
from textual.widgets import Label, Static

from . import __version__
from .demo_ai import DemoAI
from .figlet import FigletText
from .game_rules import Direction


class SplashScreen(Screen):
    """Splash screen for Snek."""

    BINDINGS = [
        ("space", "start_game", "Start Game"),
        ("d", "start_demo", "Start Demo"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the splash screen with the figlet title."""
        with Vertical(id="splash-container"):
            yield FigletText(
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

    # Display-ready stat strings — the single UI source of truth for the panel.
    # `data_bind` projects each onto a `StatDisplay` (parent → child, read-only).
    world_name: reactive[str] = reactive("")
    progress: reactive[str] = reactive("")
    foods_label: reactive[str] = reactive("")
    speed_label: reactive[str] = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self.timer: Timer | None = None
        self.sidebar_visible: bool = True
        self.demo_ai: DemoAI | None = None

    def compose(self) -> ComposeResult:
        """Compose the game screen.

        The `StatDisplay`s are created here, not in `SidePanel`, so that each
        `data_bind` resolves against *this screen's* reactives — the binding
        parent is whichever node is actively composing. `SidePanel` only lays
        them out.
        """
        yield Horizontal(
            SnakeView(),
            SidePanel(
                StatDisplay("World").data_bind(value=GameScreen.world_name),
                StatDisplay("Progress").data_bind(value=GameScreen.progress),
                StatDisplay("Total foods").data_bind(value=GameScreen.foods_label),
                StatDisplay("Speed").data_bind(value=GameScreen.speed_label),
            ),
            id="game-content",
        )

    def on_mount(self) -> None:
        """Start the game timer and set initial theme when the screen mounts."""
        self.timer = self.set_interval(self.app.game.current_interval, self.tick)
        self.app.theme = self.app.game.world_path.get_world(0).theme_name
        self._sync_reactives()

    def on_unmount(self) -> None:
        """Clean up timer when screen is unmounted."""
        self.timer.stop()

    def _restart_timer(self) -> None:
        """Restart the game timer at the game's current speed interval."""
        self.timer.stop()
        self.timer = self.set_interval(self.app.game.current_interval, self.tick)

    def _sync_reactives(self) -> None:
        """Recompute the display-ready stat strings from the game model.

        These reactives are the single UI source of truth; `data_bind`
        propagates them to the panel's `StatDisplay`s. Formatting that needs the
        world *name* or units lives here, on the screen, not in the widget.
        """
        game = self.app.game
        self.world_name = game.world_path.get_world_name(game.current_world)
        self.progress = (
            f"{game.symbols_in_current_world}/{self.app.config.symbols_per_world}"
        )
        self.foods_label = str(game.symbols_consumed)
        self.speed_label = f"{game.get_moves_per_second():.1f}/sec"

    def tick(self) -> None:
        """Advance the game one step and react to the result."""
        if self.demo_ai:
            # In demo mode, let the AI choose the direction
            ai_direction = self.demo_ai.get_next_direction()
            if ai_direction:
                self.app.game.turn(ai_direction)

        result = self.app.game.step()

        if result.world_changed:
            # Chrome follows the world: swap the app theme (kept intentionally).
            self.app.theme = self.app.game.world_path.get_world(
                result.new_world
            ).theme_name

        if result.game_over:
            # Stop the timer to prevent multiple game over modals
            self.timer.stop()
            self.app.push_screen("game_over")
            return

        if result.ate_food:
            # The model already scaled current_interval; restart at the new rate.
            self._restart_timer()

        self._sync_reactives()
        self.query_one(SnakeView).refresh()

    def action_pause(self) -> None:
        """Pause the game."""
        if not self.app.game.game_over:
            self.app.game.paused = True
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
            self.timer.resume()

    def restart_game(self) -> None:
        """Restart the game."""
        self.app.game.reset()
        if self.demo_ai:
            # Recreate AI for fresh game
            self.demo_ai = DemoAI(self.app.game)
        self._restart_timer()
        self._sync_reactives()
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
        """Compose the pause screen with the figlet title."""
        with Vertical(id="pause-container"):
            yield FigletText(
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
        """Compose the death screen with the figlet title."""
        with Vertical(id="death-container"):
            yield FigletText(
                "GAME OVER",
                font="doom",
                id="death-title",
                colors=["$primary"],
                classes="title-text",
            )
            yield Static("💀 SNEK DED! 💀", classes="death-message")
            yield Static(
                f"Foods collected: {self.app.game.symbols_consumed}",
                classes="death-prompt",
            )
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
            self.app.game.resize(game_width, game_height)
            self.refresh()

    def render(self) -> Text:
        """Render the game grid using solid block symbols for the snake."""
        width, height = self.app.game.width, self.app.game.height
        empty_cell = self.app.config.empty_cell
        food_symbol = self.app.game.food_symbol
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
                    row_parts.append(f"{food_symbol} ")
                else:
                    row_parts.append(empty_cell)
            rows.append("".join(row_parts))
        return Text("\n".join(rows))


class StatDisplay(Horizontal):
    """A labelled statistic whose value is driven by a bound reactive.

    The screen owns the (display-ready) value and binds it in via `data_bind`;
    this widget only renders the label and the latest value.
    """

    value: reactive[str] = reactive("")

    def __init__(self, label: str) -> None:
        super().__init__()
        self._label = label

    def compose(self) -> ComposeResult:
        """Compose the label and its value cell."""
        yield Label(f"{self._label}:", classes="stat-label")
        yield Label("", classes="stat-value")

    def watch_value(self, value: str) -> None:
        """React to the bound value changing."""
        self.query_one(".stat-value", Label).update(value, layout=False)


class SidePanel(Static):
    """Panel laying out the stat displays and the persistent figlet title.

    The `StatDisplay`s are built by `GameScreen` (so their bindings resolve to
    the screen's reactives) and handed in here purely for layout.
    """

    def __init__(self, *stats: StatDisplay) -> None:
        super().__init__()
        self._stats = stats
        self.styles.width = self.app.config.side_panel_width
        self.styles.min_width = self.app.config.side_panel_width

    def compose(self) -> ComposeResult:
        """Compose the side panel with the figlet title at bottom."""
        yield Vertical(
            Vertical(*self._stats, id="stats-content"),
            FigletText(
                "SNEK",
                font="small",
                id="panel-title",
                colors=["$primary"],
            ),
            id="side-panel-container",
        )
