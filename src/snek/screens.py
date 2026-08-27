"""Screen implementations for the Snek game using Textual's Screen system."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rich.segment import Segment, Segments
from textual import events, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.dom import DOMNode
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.timer import Timer
from textual.widgets import Label, Static
from typing_extensions import override

from . import __version__, clipboard, sprites
from .demo import DemoStrategy, make_demo_ai
from .figlet import FigletText
from .game import Game
from .game_rules import Direction
from .rendering import (
    CELL_BASE_WIDTH,
    compute_layout,
    fit_grid_scale,
    frame_board,
    glyph_food_tile,
    render_board,
)

if TYPE_CHECKING:
    from .app import SnakeApp

# Reused row separator for the Segments stream returned by SnakeView.render.
_NEWLINE = Segment("\n")


def _snake_app(node: DOMNode) -> SnakeApp:
    """Narrow Textual's generic app reference to this project's app type."""
    return cast("SnakeApp", node.app)


def _game_screen(node: DOMNode) -> GameScreen:
    """Return the registered game screen with its concrete type preserved."""
    return cast("GameScreen", _snake_app(node).get_screen("game"))


class SplashScreen(Screen[None]):
    """Splash screen for Snek."""

    # The large `doh` title is 85x25 before prompts and spacing. It is shown
    # only when *both* roomy breakpoint classes apply; compact terminals get a
    # 19x5 `small` title instead.
    _ROOMY_WIDTH = 100
    _ROOMY_HEIGHT = 40
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (_ROOMY_WIDTH, "-wide")]
    VERTICAL_BREAKPOINTS = [(0, "-short"), (_ROOMY_HEIGHT, "-tall")]

    BINDINGS = [
        ("space", "start_game", "Start Game"),
        ("d", "start_demo", "Start Demo"),
        ("q", "quit", "Quit"),
    ]

    @override
    def compose(self) -> ComposeResult:
        """Compose the splash screen with the figlet title."""
        app = _snake_app(self)
        with Vertical(id="splash-container"):
            yield FigletText(
                "SNEK",
                font="doh",
                id="splash-title",
                classes="title-text",
                colors=["$primary", "$panel"],
                # FigletText owns preference, visibility, and timer lifecycle;
                # the CSS breakpoints decide whether this large title is shown.
                animate=True,
            )
            yield FigletText(
                "SNEK",
                font="small",
                id="splash-title-compact",
                classes="title-text",
                colors=["$primary", "$panel"],
            )
            yield Static(
                f"Press SPACE to start or D for the {app.demo_strategy} demo.",
                id="splash-start-prompt",
                classes="splash-prompt",
            )
            yield Static(
                "Use arrow or WASD keys to move, Space to pause, Q to quit.",
                id="splash-controls-prompt",
                classes="splash-prompt",
            )
            yield Static(
                f"v{__version__}", id="splash-version", classes="version-display"
            )

    def on_screen_suspend(self) -> None:
        """Pause title work while another screen covers the splash."""
        for title in self.query(FigletText):
            title.pause_animation()

    def on_screen_resume(self) -> None:
        """Resume eligible visible titles without creating another timer."""
        for title in self.query(FigletText):
            title.resume_animation()

    def action_start_game(self) -> None:
        """Start a fresh game under user control."""
        game_screen = _game_screen(self)
        game_screen.start_new_game(demo=False)
        self.app.push_screen("game")

    def action_start_demo(self) -> None:
        """Start a fresh game in demo mode."""
        game_screen = _game_screen(self)
        game_screen.start_new_game(demo=True)
        self.app.push_screen("game")

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()


class GameScreen(Screen[None]):
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
        ("question_mark", "diagnostics", "Diagnostics"),
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
        self.demo_ai: DemoStrategy | None = None

    @override
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
        app = _snake_app(self)
        self.timer = self.set_interval(app.game.current_interval, self.tick)
        app.theme = app.game.world_path.get_world(0).theme_name
        self._sync_reactives()

    def on_unmount(self) -> None:
        """Clean up timer when screen is unmounted."""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None

    def _restart_timer(self) -> None:
        """Restart the game timer at the game's current speed interval."""
        if self.timer is not None:
            self.timer.stop()
        self.timer = self.set_interval(
            _snake_app(self).game.current_interval, self.tick
        )

    def _sync_reactives(self) -> None:
        """Recompute the display-ready stat strings from the game model.

        These reactives are the single UI source of truth; `data_bind`
        propagates them to the panel's `StatDisplay`s. Formatting that needs the
        world *name* or units lives here, on the screen, not in the widget.
        """
        app = _snake_app(self)
        game = app.game
        self.world_name = game.world_path.get_world_name(game.current_world)
        self.progress = (
            f"{game.symbols_in_current_world}/{app.config.symbols_per_world}"
        )
        self.foods_label = str(game.symbols_consumed)
        self.speed_label = f"{game.get_moves_per_second():.1f}/sec"

    def tick(self) -> None:
        """Advance the game one step and react to the result."""
        app = _snake_app(self)
        if self.demo_ai:
            # In demo mode, let the demo strategy choose the direction
            ai_direction = self.demo_ai.get_next_direction()
            if ai_direction:
                app.game.turn(ai_direction)

        result = app.game.step()

        if result.world_changed and result.new_world is not None:
            # Chrome follows the world: swap the app theme (kept intentionally).
            app.theme = app.game.world_path.get_world(result.new_world).theme_name

        if result.game_over:
            # Stop the timer to prevent multiple game over modals.
            if self.timer is not None:
                self.timer.stop()
            # Push a FRESH modal instance (not the registered singleton) so its
            # compose() re-reads the current game: the win/death banner and the
            # final food count reflect *this* game, not a cached earlier one.
            app.push_screen(GameOverModal())
            return

        if result.ate_food:
            # The model already scaled current_interval; restart at the new rate.
            self._restart_timer()

        self._sync_reactives()
        self.query_one(SnakeView).refresh()

    def action_pause(self) -> None:
        """Pause the game."""
        app = _snake_app(self)
        if not app.game.game_over:
            app.game.paused = True
            if self.timer is not None:
                self.timer.pause()
            app.push_screen("pause")

    def action_diagnostics(self) -> None:
        """Pause the game and show the live diagnostics overlay.

        Pushed as a fresh instance (not a registered singleton) so its key/value
        snapshot reflects the game's current state each time it's opened.
        """
        app = _snake_app(self)
        if not app.game.game_over:
            app.game.paused = True
            if self.timer is not None:
                self.timer.pause()
            app.push_screen(DiagnosticsModal())

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

        _snake_app(self).game.turn(Direction[dir_name])
        # Force a refresh after key press to show immediate response
        self.query_one(SnakeView).refresh()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def resume_game(self) -> None:
        """Resume the game after pause."""
        app = _snake_app(self)
        if app.game.paused:
            app.game.paused = False
            if self.timer is not None:
                self.timer.resume()

    def restart_game(self) -> None:
        """Restart the game."""
        app = _snake_app(self)
        app.game.reset()
        if self.demo_ai:
            # Recreate the demo strategy for a fresh game, keeping the selection.
            self.demo_ai = make_demo_ai(app.game, app.demo_strategy)
        self._restart_timer()
        self._sync_reactives()
        # Update theme to initial world before refreshing view
        app.theme = app.game.world_path.get_world(0).theme_name
        self.query_one(SnakeView).refresh()

    def establish_grid(self, width: int, height: int) -> None:
        """Establish dimensions from the first layout before play begins.

        `SnakeView` invokes this once in its lifetime. The model is still a
        fresh length-one game, so resetting it at the selected dimensions loses
        no play state. Demo strategies are recreated because some cache grid
        topology.
        """
        app = _snake_app(self)
        app.game.reset(width=width, height=height)
        if self.demo_ai:
            self.demo_ai = make_demo_ai(app.game, app.demo_strategy)
        self._sync_reactives()

    def start_new_game(self, demo: bool) -> None:
        """Begin a fresh game from the splash, clearing any prior end-state.

        The `GameScreen` is an installed singleton — mounted once and reused — so
        `on_mount` does NOT run again when the screen is re-shown after a game
        ends, and the timer stopped on game-over is never restarted on its own.
        Without an explicit reset a second game would inherit the previous game's
        `game_over`/`won`/score: the board freezes (`Game.step` early-returns
        while `game_over`) and a stale "you win" banner can appear. So reset the
        model, set the mode, and — if the screen is already mounted — re-establish
        the timer, theme and view. (On the very first start the timer is still
        `None`; `on_mount` does this once the screen is pushed.)
        """
        app = _snake_app(self)
        app.game.reset()
        self.demo_ai = make_demo_ai(app.game, app.demo_strategy) if demo else None
        if self.timer is not None:
            self._restart_timer()
            app.theme = app.game.world_path.get_world(0).theme_name
            self._sync_reactives()
            self.query_one(SnakeView).refresh()


class PauseModal(ModalScreen[None]):
    """Modal screen shown when game is paused."""

    BINDINGS = [
        ("space", "resume", "Resume"),
        ("q", "quit", "Quit"),
    ]

    @override
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
        game_screen = _game_screen(self)
        game_screen.resume_game()
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()


class DiagnosticsModal(ModalScreen[None]):
    """A pause-style overlay that shows live config and game state for debugging.

    Opened with `?` from the game (which also pauses); SPACE resumes, mirroring
    the pause modal. Parameters are read in `compose`, so each open reflects the
    current state.
    """

    BINDINGS = [
        ("space", "resume", "Resume"),
        ("c", "copy", "Copy"),
        ("q", "quit", "Quit"),
    ]

    @override
    def compose(self) -> ComposeResult:
        """Compose fixed actions around a vertically scrollable diagnostics body."""
        with Vertical(id="diagnostics-container"):
            yield FigletText(
                "DIAGNOSTICS",
                font="doom",
                id="diagnostics-title",
                colors=["$primary"],
                classes="title-text",
            )
            yield Static("C copy · SPACE close · ↑/↓ scroll", id="diagnostics-prompt")
            with VerticalScroll(id="diagnostics-scroll", can_focus=True):
                yield Static(self._params_text(), id="diagnostics-params")

    def _params_text(self) -> str:
        """Build the aligned key/value snapshot of config and live game state."""
        app = _snake_app(self)
        game = app.game
        config = app.config
        game_screen = _game_screen(self)
        view = game_screen.query_one(SnakeView)

        # `None` entries render as blank spacer lines between sections.
        rows: list[tuple[str, str] | None] = [
            ("terminal (cells)", f"{app.size.width} x {app.size.height}"),
            ("snake view", f"{view.size.width} x {view.size.height}"),
            ("cell scale (k)", str(view._scale)),
            None,
            ("sizing mode", config.sizing_mode),
            ("cell scale setting", str(config.cell_scale)),
            ("logical grid", f"{game.width} x {game.height}"),
            ("grid cap", f"{config.max_grid_width} x {config.max_grid_height}"),
            ("grid min", f"{config.min_game_width} x {config.min_game_height}"),
            (
                "grid default",
                f"{config.default_grid_width} x {config.default_grid_height}",
            ),
            ("food sprites", str(config.food_sprites)),
            None,
            ("interval", f"{game.current_interval:.4f} s"),
            ("speed", f"{game.get_moves_per_second():.1f} /sec"),
            ("initial interval", f"{config.initial_speed_interval} s"),
            ("speed factor", str(config.speed_increase_factor)),
            ("min interval", f"{config.min_speed_interval} s"),
            None,
            (
                "world",
                f"{game.current_world}  "
                f"{game.world_path.get_world_name(game.current_world)}",
            ),
            ("symbols / world", str(config.symbols_per_world)),
            ("in world", str(game.symbols_in_current_world)),
            ("total foods", str(game.symbols_consumed)),
            None,
            ("snake length", str(len(game.snake))),
            ("direction", game.direction.name),
            ("max buffered turns", str(config.max_buffered_turns)),
            ("demo strategy", app.demo_strategy),
            ("demo active", str(game_screen.demo_ai is not None)),
        ]

        key_width = max(len(row[0]) for row in rows if row is not None)
        lines = [
            "" if row is None else f"{row[0]:>{key_width}} : {row[1]}" for row in rows
        ]
        return "\n".join(lines)

    @work(exclusive=True, exit_on_error=False)
    async def action_copy(self) -> None:
        """Copy the diagnostics text to the system clipboard.

        Prefers a local clipboard utility and falls back to OSC 52 (see
        `clipboard.copy_text`), so it works even where the terminal ignores OSC
        52. The toast names the method used.
        """
        result = await clipboard.copy_text(_snake_app(self), self._params_text())
        if result.method == clipboard.METHOD_OSC52:
            # OSC 52 is often ignored (no local clipboard tool, tmux, etc.), so
            # warn rather than silently claim success.
            self.notify(
                f"{result.detail}; copied via terminal escape (OSC 52). "
                "The terminal may not support it.",
                title="Clipboard",
                severity="warning",
                timeout=6,
            )
        else:
            self.notify(f"Diagnostics copied to {result.method}", timeout=2)

    def action_resume(self) -> None:
        """Resume the game (mirrors the pause modal)."""
        game_screen = _game_screen(self)
        game_screen.resume_game()
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()


class GameOverModal(ModalScreen[None]):
    """Modal screen shown when snek dies."""

    BINDINGS = [
        ("space", "restart", "Restart"),
        ("enter", "menu", "Main Menu"),
        ("q", "quit", "Quit"),
    ]

    @override
    def compose(self) -> ComposeResult:
        """Compose the end-of-game screen with the figlet title.

        The same modal serves death and victory: when the board has been filled
        (`app.game.won`) it shows a win banner instead of the death message.
        """
        app = _snake_app(self)
        won = app.game.won
        with Vertical(id="death-container"):
            yield FigletText(
                "YOU WIN" if won else "GAME OVER",
                font="doom",
                id="death-title",
                colors=["$primary"],
                classes="title-text",
            )
            yield Static(
                "🎉 BOARD FILLED! 🎉" if won else "💀 SNEK DED! 💀",
                classes="death-message",
            )
            yield Static(
                f"Foods collected: {app.game.symbols_consumed}",
                classes="death-prompt",
            )
            yield Static(
                "Press SPACE to restart, ENTER for main menu, or Q to quit",
                classes="death-prompt",
            )

    def action_restart(self) -> None:
        """Restart the game in the same mode (user/demo).

        Pop only this modal so we land back on the (now reset) GameScreen and
        resume play. Popping twice would drop through to the splash while the
        restarted game ticks on invisibly underneath.
        """
        game_screen = _game_screen(self)
        game_screen.restart_game()
        self.app.pop_screen()

    def action_menu(self) -> None:
        """Return to the main menu (splash): pop this modal and the GameScreen."""
        self.app.pop_screen()
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()


class SnakeView(Static):
    """Renders the game as text.

    The first valid layout establishes the logical grid. After that this widget
    only changes how big each cell is drawn, so viewport changes cannot corrupt
    model coordinates. CSS (`content-align: center middle`) centres the scaled
    board in the leftover space.
    """

    # How many terminal characters draw one logical cell, per axis-unit. Updated
    # on resize; the board is drawn at this scale.
    _scale: int = 1
    _grid_established: bool = False

    def on_resize(self, event: events.Resize) -> None:
        """Establish the logical grid once, then make every resize visual-only."""
        app = _snake_app(self)
        if self.size.width > 0 and self.size.height > 0:
            if not self._grid_established:
                grid_width, grid_height, self._scale = compute_layout(
                    self.size.width, self.size.height, app.config
                )
                cast(GameScreen, self.screen).establish_grid(grid_width, grid_height)
                self._grid_established = True
            else:
                game = app.game
                self._scale = fit_grid_scale(
                    self.size.width,
                    self.size.height,
                    game.width,
                    game.height,
                    app.config.cell_scale,
                )
            self.refresh()

    @override
    def render(self) -> Segments:
        """Render the game grid: solid blocks for the snake, sprite/glyph food."""
        app = _snake_app(self)
        game = app.game
        empty_cell = app.config.empty_cell
        food_tile = self._food_tile(game)
        lines = render_board(
            game.width,
            game.height,
            set(game.snake),
            game.food,
            self._scale,
            game.config.snake_block,
            empty_cell,
            food_tile,
        )
        # Frame the capped board to make its boundary (and the wrap-around)
        # visible inside the letterbox margin. "fill" mode covers the terminal
        # edge-to-edge, so there's no margin to frame.
        board_cols = CELL_BASE_WIDTH * game.width * self._scale
        board_rows = game.height * self._scale
        if (
            app.config.sizing_mode == "cap"
            and self.size.width >= board_cols + 2
            and self.size.height >= board_rows + 2
        ):
            lines = frame_board(lines, board_cols)
        flat: list[Segment] = []
        for line in lines:
            flat.extend(line)
            flat.append(_NEWLINE)
        if flat:
            flat.pop()  # no trailing newline after the last row
        return Segments(flat)

    def _food_tile(self, game: Game) -> list[list[Segment]]:
        """Pick the food rendering: a pixel sprite when big enough, else the glyph.

        At scale 1 (and when sprites are disabled) the cell is too small for pixel
        art, so we keep the themed Unicode glyph.
        """
        config = _snake_app(self).config
        if config.food_sprites and self._scale >= sprites.MIN_SPRITE_SCALE:
            return sprites.food_tile(
                sprites.get_food_sprite(game.current_world), self._scale
            )
        return glyph_food_tile(game.food_symbol, config.empty_cell, self._scale)


class StatDisplay(Horizontal):
    """A labelled statistic whose value is driven by a bound reactive.

    The screen owns the (display-ready) value and binds it in via `data_bind`;
    this widget only renders the label and the latest value.
    """

    value: reactive[str] = reactive("")

    def __init__(self, label: str) -> None:
        super().__init__()
        self._label = label

    @override
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
        side_panel_width = _snake_app(self).config.side_panel_width
        self.styles.width = side_panel_width
        self.styles.min_width = side_panel_width

    @override
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
