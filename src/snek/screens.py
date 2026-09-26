"""Screen implementations for the Snek game using Textual's Screen system."""

from __future__ import annotations

import textwrap
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from rich.cells import cell_len
from rich.segment import Segment
from textual import events, work
from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical, VerticalScroll
from textual.dom import DOMNode
from textual.geometry import Region
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.strip import Strip
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Label, Static
from typing_extensions import Self, override

from . import __version__, clipboard, sprites
from .config import GameConfig
from .demo import DemoStrategy, make_demo_ai
from .figlet import FigletText
from .game import Game, StepResult
from .game_rules import Direction, Position
from .modes import Settings, describe
from .rendering import (
    CELL_BASE_WIDTH,
    FRAME_MARGIN,
    SMOOTH_EMPTY_CELL,
    SMOOTH_SNAKE_BLOCK,
    PartialCell,
    board_fits,
    board_size,
    compute_layout,
    fit_grid_scale,
    frame_rule,
    frame_side,
    glyph_food_tile,
    motion_cells,
    motion_units,
    render_board_row,
)
from .settings import MODE_ROW, ROWS, widest_help
from .timing import StepClock, next_wake_delay

if TYPE_CHECKING:
    from .app import SnakeApp

# Textual's default screen-update rate. The loop never wakes more often than
# this; without interpolation it wakes only at step deadlines.
_FRAME_INTERVAL = 1 / 60

# Interpolate only when a step spans at least this many frames. Faster steps
# would show few, unevenly timed increments, and whole cells read better.
_MIN_SMOOTH_FRAMES = 2


# Spare cells beside the longest help line, so it never touches the box's edges.
_HELP_MARGIN = 4


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

    # The start prompt, in the two halves it splits into when it can't fit.
    _START_PROMPT = (
        "Press SPACE to start, D to run the demo,",
        "←/→ to change mode, or S for detailed settings.",
    )

    BINDINGS = [
        ("space", "start_game", "Start Game"),
        ("d", "start_demo", "Start Demo"),
        ("s", "settings", "Settings"),
        ("left", "mode(-1)", "Mode"),
        ("right", "mode(1)", "Mode"),
        ("q", "quit", "Quit"),
    ]

    @override
    def compose(self) -> ComposeResult:
        """Compose the splash screen with the figlet title."""
        with Vertical(id="splash-container"):
            # Textual aligns a container's children as one block, and the
            # full-width prompts make that block span the screen. Each title
            # gets its own Center so it is centred independently of them.
            with Center():
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
            with Center():
                yield FigletText(
                    "SNEK",
                    font="small",
                    id="splash-title-compact",
                    classes="title-text",
                    colors=["$primary", "$panel"],
                )
            yield Static(id="splash-start-prompt", classes="splash-prompt")
            yield Static(
                "Gameplay: use arrow or WASD keys to move, Space to pause, Q to quit.",
                id="splash-controls-prompt",
                classes="splash-prompt",
            )
            yield Static(id="splash-mode")
            yield Static(id="splash-mode-help", classes="splash-prompt")
            yield Static(
                f"v{__version__}", id="splash-version", classes="version-display"
            )

    def on_mount(self) -> None:
        """Show the mode the settings are in."""
        self._show_mode()

    def on_resize(self, event: events.Resize) -> None:
        """Fit the start prompt: one line where it fits, else two balanced ones.

        Left to wrap on its own, the prompt would leave one word on its second
        line at the 80-column minimum.
        """
        first, second = self._START_PROMPT
        one_line = f"{first} {second}"
        text = (
            one_line if cell_len(one_line) <= event.size.width else f"{first}\n{second}"
        )
        self.query_one("#splash-start-prompt", Static).update(text)

    def _show_mode(self) -> None:
        """Show the current mode (or Custom) and what it is."""
        name = MODE_ROW.value_text(_snake_app(self).settings)
        self.query_one("#splash-mode", Static).update(f"◂ {name} ▸")
        self.query_one("#splash-mode-help", Static).update(describe(name))

    def action_mode(self, delta: int) -> None:
        """Cycle the mode, applying its settings for the next game."""
        app = _snake_app(self)
        app.apply_settings(MODE_ROW.step(app.settings, delta))
        self._show_mode()

    def on_screen_suspend(self) -> None:
        """Pause title work while another screen covers the splash."""
        for title in self.query(FigletText):
            title.pause_animation()

    def on_screen_resume(self) -> None:
        """Resume eligible visible titles without creating another timer.

        Also refresh the mode, which the settings screen may have changed.
        """
        for title in self.query(FigletText):
            title.resume_animation()
        self._show_mode()

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

    def action_settings(self) -> None:
        """Open the settings, which apply from the next game."""
        self.app.push_screen(SettingsModal())

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
        ("escape", "menu", "Main Menu"),
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
        # `timer` is the single loop timer, created only by `_arm()`: a one-shot
        # at the next step deadline or, while interpolating, the next substep.
        # `_clock` decides when a model step is due. `_last_frame` is None until
        # the first wake after a (re)start or resume, so paused time never counts.
        # `_motion` is the step being interpolated, if any. `_generation` tags
        # each armed wake so a stale one can be ignored (see `_on_wake`).
        self.timer: Timer | None = None
        self._generation: int = 0
        self._clock = StepClock()
        self._last_frame: float | None = None
        self._motion: StepResult | None = None
        # Injectable so tests can drive frames without patching the global clock.
        self._now: Callable[[], float] = time.monotonic
        self.sidebar_visible: bool = True
        self.demo_ai: DemoStrategy | None = None
        # True while the terminal is too small to draw the board (see
        # `hold_for_size`); the loop stays stopped until there is room.
        self._held: bool = False

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
        self._restart_loop()
        app.theme = app.game.world_path.get_world(0).theme_name
        self._sync_reactives()

    def on_unmount(self) -> None:
        """Clean up timer when screen is unmounted."""
        self._disarm()

    def _restart_loop(self) -> None:
        """(Re)start the loop with an empty step clock."""
        self._disarm()
        self._clock.reset()
        self._last_frame = None
        self._motion = None
        self._arm()

    def _substeps(self, interval: float) -> int:
        """How many increments the board draws each step in: 1 means whole cells."""
        if interval < _MIN_SMOOTH_FRAMES * _FRAME_INTERVAL:
            return 1
        return self.query_one(SnakeView).motion_units()

    def _arm(self) -> None:
        """Schedule the next wake; the only place that creates loop timers.

        A one-shot timer fires exactly when the next step is due or, while
        interpolating, at the next substep boundary. Steps and the increments
        between them keep an even rhythm instead of snapping to a frame grid.
        """
        game = _snake_app(self).game
        self._disarm()
        if game.game_over or game.paused or self._held:
            return
        if self._last_frame is None:
            # Count from now, so the first wake after a (re)start or resume
            # credits the time spent waiting for it.
            self._last_frame = self._now()
        delay = next_wake_delay(
            game.current_interval,
            self._clock.accumulated,
            _FRAME_INTERVAL,
            self._substeps(game.current_interval),
        )
        generation = self._generation
        self.timer = self.set_timer(delay, lambda: self._on_wake(generation))

    def _disarm(self) -> None:
        """Stop and forget the loop timer, if any, and void any wake it queued."""
        self._generation += 1
        if self.timer is not None:
            self.timer.stop()
            self.timer = None

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

    def _on_wake(self, generation: int) -> None:
        """Handle a timer wake unless the loop was stopped or re-armed since.

        Textual queues a timer's callback on the screen rather than calling it,
        so stopping a timer that has already fired cannot recall its wake.
        """
        if generation == self._generation:
            self._on_frame()

    def _on_frame(self) -> None:
        """Run every model step that has come due, draw, then schedule the next wake.

        The step interval is re-read before each step, so eating food speeds up
        the very next step. A stale timer firing while paused or after the game
        ends does nothing and schedules nothing.
        """
        game = _snake_app(self).game
        if game.game_over or game.paused:
            return
        self._advance_clock()
        steps = 0
        result: StepResult | None = None
        while self._clock.take_step(game.current_interval):
            result = self._step()
            if result is None:
                return
            steps += 1
        if steps:
            self._sync_reactives()
            # Several steps in one wake means the loop fell behind; draw whole.
            self._motion = result if steps == 1 else None
        self._draw()
        self._arm()

    def _draw(self) -> None:
        """Update the board, part way through the current step when interpolating."""
        interval = _snake_app(self).game.current_interval
        motion = self._motion if self._substeps(interval) > 1 else None
        self.query_one(SnakeView).update_board(motion, self._clock.progress(interval))

    def _advance_clock(self) -> None:
        """Credit the step clock with the wall time since the previous wake."""
        now = self._now()
        elapsed = 0.0 if self._last_frame is None else now - self._last_frame
        self._last_frame = now
        self._clock.advance(elapsed)

    def tick(self) -> None:
        """Advance the game exactly one step and redraw it whole."""
        if self._step() is not None:
            self._motion = None
            self._sync_reactives()
            self.query_one(SnakeView).update_board()

    def _step(self) -> StepResult | None:
        """Advance the model one step; return None once the game has ended."""
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
            # Stop the loop to prevent multiple game over modals, and settle
            # any part-drawn step so the final board is whole.
            self._disarm()
            self._motion = None
            self.query_one(SnakeView).update_board()
            # Push a FRESH modal instance (not the registered singleton) so its
            # compose() re-reads the current game: the win/death banner and the
            # final food count reflect *this* game, not a cached earlier one.
            app.push_screen(GameOverModal())
            return None
        return result

    def action_pause(self) -> None:
        """Pause the game."""
        app = _snake_app(self)
        if not app.game.game_over:
            self._pause_loop()
            app.push_screen("pause")

    def _pause_loop(self) -> None:
        """Pause the model and stop the loop, keeping progress towards the next step.

        Between deadline wakes no frames run, so the time since the last wake is
        credited now; resuming then waits only for the rest of the interval.
        """
        game = _snake_app(self).game
        if self.timer is not None and not game.paused:
            self._advance_clock()
        game.paused = True
        self._disarm()

    def hold_for_size(self, held: bool) -> None:
        """Stop the loop while the terminal is too small, and restart it after.

        Like pausing, the time already waited is credited and the held time is
        not; unlike pausing, the model is untouched, so a pause taken while held
        still needs resuming.
        """
        if held == self._held:
            return
        self._held = held
        if held:
            if self.timer is not None:
                self._advance_clock()
            self._disarm()
        else:
            self._last_frame = None
            self._arm()

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Offer the main menu only while the board is held for size."""
        if action == "menu":
            return self._held
        return True

    def action_menu(self) -> None:
        """Leave a held game for the main menu, e.g. to turn sprites off."""
        self.app.pop_screen()

    def action_diagnostics(self) -> None:
        """Pause the game and show the live diagnostics overlay.

        Pushed as a fresh instance (not a registered singleton) so its key/value
        snapshot reflects the game's current state each time it's opened.
        """
        app = _snake_app(self)
        if not app.game.game_over:
            self._pause_loop()
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

        # Turns are buffered until the next tick, so there is nothing new to
        # draw yet; `tick` refreshes the board once the turn is applied.
        _snake_app(self).game.turn(Direction[dir_name])

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def resume_game(self) -> None:
        """Resume the game after pause."""
        app = _snake_app(self)
        if app.game.paused:
            app.game.paused = False
            # Don't count the paused time as elapsed game time.
            self._last_frame = None
            self._arm()

    def restart_game(self) -> None:
        """Restart the game."""
        app = _snake_app(self)
        app.game.reset()
        if self.demo_ai:
            # Recreate the demo strategy for a fresh game, keeping the selection.
            self.demo_ai = make_demo_ai(app.game, app.demo_strategy)
        self._restart_loop()
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
        the loop, theme and view. (On the very first start the screen is not yet
        mounted; `on_mount` does this once the screen is pushed.)
        """
        app = _snake_app(self)
        app.game.reset()
        self.demo_ai = make_demo_ai(app.game, app.demo_strategy) if demo else None
        if self.is_mounted:
            # Settings may have changed the layout since the last game.
            self.query_one(SnakeView).relayout()
            self._restart_loop()
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
            (
                "board fits",
                "yes"
                if view._needed is None
                else f"no, needs {view._needed[0]} x {view._needed[1]}",
            ),
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
            ("food type", config.food_type),
            ("walls", str(config.walls)),
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
            ("start length", str(config.start_length)),
            ("growing in", str(game.pending_growth)),
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


class SettingsModal(ModalScreen[None]):
    """Session settings, opened with S from the splash.

    Up and down pick a setting; left and right change it (see `settings.ROWS`).
    Changes build a draft, which may be invalid (e.g. food sprites at cell scale
    one) so that every row can step through all its choices; the reason shows in
    red below the help. ENTER applies a valid draft for the next game and does
    nothing while it is invalid; ESC discards it. A fresh instance is pushed
    each time so it starts from the current settings.
    """

    BINDINGS = [
        ("up", "move(-1)", "Previous"),
        ("down", "move(1)", "Next"),
        ("w", "move(-1)", None),
        ("s", "move(1)", None),
        ("left", "change(-1)", "Change"),
        ("right", "change(1)", "Change"),
        ("a", "change(-1)", None),
        ("d", "change(1)", None),
        ("enter", "apply", "Apply"),
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.selected = 0
        self.draft: Settings | None = None

    @override
    def compose(self) -> ComposeResult:
        """Compose the title, one line per setting, and the selected one's help."""
        with Vertical(id="settings-container"):
            # Textual aligns a container's children as one block, so the title
            # and the (fixed-width) help line each need a Center of their own.
            with Center():
                yield FigletText(
                    "SETTINGS",
                    font="doom",
                    id="settings-title",
                    colors=["$primary"],
                    classes="title-text",
                )
            yield Static(
                "↑/↓ choose · ←/→ change · ENTER apply · ESC back",
                id="settings-prompt",
            )
            with Center(id="settings-rows-center"), Vertical(id="settings-rows"):
                for index in range(len(ROWS)):
                    yield Static(id=f"setting-{index}", classes="setting-row")
            with Center():
                yield Static(id="settings-help")
            with Center():
                yield Static(id="settings-error")

    def on_mount(self) -> None:
        """Start a draft from the current settings and size the help lines."""
        self.draft = _snake_app(self).settings
        width = widest_help(self.draft) + _HELP_MARGIN
        for line in ("#settings-help", "#settings-error"):
            self.query_one(line, Static).styles.width = width
        self._show()

    @property
    def _draft(self) -> Settings:
        """The settings being edited (set on mount)."""
        assert self.draft is not None
        return self.draft

    def _show(self) -> None:
        """Redraw every row, marking the selected one, its help and any error."""
        settings = self._draft
        label_width = max(len(row.label) for row in ROWS)
        # Pad every value to the widest the settings can show, so the block
        # keeps one width (and stays centred) as values change.
        value_width = max(
            len(text)
            for row in ROWS
            for text in (row.value_text(settings), *map(row.show, row.choices))
        )
        for index, row in enumerate(ROWS):
            line = self.query_one(f"#setting-{index}", Static)
            selected = index == self.selected
            marker = "▸" if selected else " "
            value = f"{row.value_text(settings):^{value_width}}"
            shown = f"◂ {value} ▸" if selected else f"  {value}  "
            line.update(f"{marker} {row.label:<{label_width}}   {shown}")
            line.set_class(selected, "-selected")
        self.query_one("#settings-help", Static).update(
            ROWS[self.selected].help_text(settings)
        )
        error = settings.error()
        self.query_one("#settings-error", Static).update(
            "" if error is None else error[0].upper() + error[1:] + "."
        )

    def action_move(self, delta: int) -> None:
        """Select the previous or next setting, wrapping round."""
        self.selected = (self.selected + delta) % len(ROWS)
        self._show()

    def action_change(self, delta: int) -> None:
        """Step the selected setting in the draft, even into an invalid one."""
        self.draft = ROWS[self.selected].step(self._draft, delta)
        self._show()

    def action_apply(self) -> None:
        """Apply a valid draft and return to the splash; ignore an invalid one."""
        if self._draft.error() is not None:
            return
        _snake_app(self).apply_settings(self._draft)
        self.app.pop_screen()

    def action_back(self) -> None:
        """Discard the draft and return to the splash."""
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
            # A Center of its own centres the title across the screen and widens
            # the container past it, so the restart prompt fits on one line.
            with Center():
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


@dataclass(frozen=True)
class BoardState:
    """The board contents a `SnakeView` last drew.

    Every line is rendered from this snapshot rather than from the live game, so
    the view always knows exactly what is on screen and can repaint only the
    cells that differ from the next snapshot. `partial` holds the cells drawn
    part way through an interpolated step.
    """

    width: int
    height: int
    snake: frozenset[Position]
    food: Position
    world: int
    food_symbol: str
    partial: Mapping[Position, PartialCell] = field(default_factory=dict)

    @classmethod
    def capture(
        cls, game: Game, partial: Mapping[Position, PartialCell] | None = None
    ) -> BoardState:
        """Snapshot the parts of `game` the board draws."""
        return cls(
            game.width,
            game.height,
            frozenset(game.snake),
            game.food,
            game.current_world,
            game.food_symbol,
            {} if partial is None else partial,
        )


@dataclass(frozen=True)
class BoardGeometry:
    """Where the (optionally framed) board sits inside the view."""

    left: int
    top: int
    board_cols: int
    board_rows: int
    framed: bool

    @property
    def board_left(self) -> int:
        """First column of the board proper, inside any frame."""
        return self.left + self.framed

    @property
    def board_top(self) -> int:
        """First row of the board proper, inside any frame."""
        return self.top + self.framed


def _layout_key(config: GameConfig) -> tuple[object, ...]:
    """The settings that decide the logical grid and how the board is fitted."""
    return (
        config.sizing_mode,
        config.cell_scale,
        config.max_grid_width,
        config.max_grid_height,
        config.walls,
        config.food_type,
    )


class SnakeView(Widget):
    """Renders the game board line by line (Textual's Line API).

    The first valid layout establishes the logical grid. After that this widget
    only changes how big each cell is drawn, so viewport changes cannot corrupt
    model coordinates. The widget centres the scaled board itself.

    Lines are drawn from a `BoardState` snapshot. `update_board()` takes a new
    snapshot and refreshes only the cells that changed, so Textual re-renders
    just those lines and writes just those cells to the terminal. A full
    `refresh()` re-snapshots the live game, drawn whole.

    Given the step just taken and how far the clock is through the next one,
    `update_board()` draws the head and vacated tail cells part filled, so the
    snake slides between cells (see `rendering.motion_cells`).
    """

    # How many terminal characters draw one logical cell, per axis-unit. Updated
    # on resize; the board is drawn at this scale.
    _scale: int = 1
    _grid_established: bool = False
    # The layout settings the grid was established with (see `_layout_key`).
    _established_for: tuple[object, ...] | None = None
    # The snapshot being drawn; None means "take a fresh one on next use".
    _drawn: BoardState | None = None
    # Board rows built for one snapshot at one scale, keyed by logical row. A
    # cell spans `scale` terminal rows, and each is rendered as its own line.
    _rows_for: tuple[BoardState, int] | None = None
    _rows: dict[int, list[list[Segment]]] | None = None
    # The terminal size the board needs, while it is too small to draw the board
    # at the smallest scale the config allows; None while the board fits.
    _needed: tuple[int, int] | None = None

    def on_resize(self, event: events.Resize) -> None:
        """Establish the logical grid once, then make every resize visual-only."""
        self._layout()

    def relayout(self) -> None:
        """Establish the grid again if the layout settings changed since.

        Called when a new game starts, which is the only time the grid may
        change. Settings changed on the splash take effect here.
        """
        config = _snake_app(self).config
        if self._grid_established and self._established_for != _layout_key(config):
            self._grid_established = False
            self._layout()

    def _layout(self) -> None:
        """Fit the board to the view, establishing the grid if it isn't yet.

        With walls the frame is part of the game, so the board is fitted inside
        the space left once the frame has room.
        """
        app = _snake_app(self)
        if self.size.width > 0 and self.size.height > 0:
            reserve = FRAME_MARGIN if app.config.walls else 0
            avail_cols = max(1, self.size.width - reserve)
            avail_rows = max(1, self.size.height - reserve)
            game_screen = cast(GameScreen, self.screen)
            if not self._grid_established:
                grid_width, grid_height, self._scale = compute_layout(
                    avail_cols, avail_rows, app.config
                )
                game_screen.establish_grid(grid_width, grid_height)
                self._grid_established = True
                self._established_for = _layout_key(app.config)
            else:
                game = app.game
                self._scale = fit_grid_scale(
                    avail_cols,
                    avail_rows,
                    game.width,
                    game.height,
                    app.config.cell_scale,
                    app.config.min_cell_scale,
                )
            self._needed = self._terminal_needed(avail_cols, avail_rows, reserve)
            game_screen.hold_for_size(self._needed is not None)
            self.refresh()

    def _terminal_needed(
        self, avail_cols: int, avail_rows: int, reserve: int
    ) -> tuple[int, int] | None:
        """The terminal size the board needs, or None if it fits.

        Only food sprites set a scale floor above one, so only they can make the
        terminal too small; otherwise the board is drawn at scale one, clipped
        if need be (below the supported 80x24).
        """
        app = _snake_app(self)
        config, game = app.config, app.game
        if not config.uses_sprites or board_fits(
            avail_cols, avail_rows, game.width, game.height, config.min_cell_scale
        ):
            return None
        cols, rows = board_size(game.width, game.height, config.min_cell_scale)
        # Whatever the terminal gives to everything but the board, it still needs.
        return (
            app.size.width + cols + reserve - self.size.width,
            app.size.height + rows + reserve - self.size.height,
        )

    @property
    def too_small(self) -> bool:
        """Whether the terminal is too small to draw the board."""
        return self._needed is not None

    @override
    def refresh(
        self,
        *regions: Region,
        repaint: bool = True,
        layout: bool = False,
        recompose: bool = False,
    ) -> Self:
        """Refresh as usual; a full refresh also re-snapshots the live game."""
        if not regions:
            self._drawn = None
        return super().refresh(
            *regions, repaint=repaint, layout=layout, recompose=recompose
        )

    def motion_units(self) -> int:
        """Increments per step when interpolating at this scale; 1 when disabled.

        Partial cells are drawn with block elements, so interpolation needs the
        default snake and blank glyphs as well as `smooth_motion`.
        """
        config = _snake_app(self).config
        if (
            config.smooth_motion
            and config.snake_block == SMOOTH_SNAKE_BLOCK
            and config.empty_cell == SMOOTH_EMPTY_CELL
        ):
            return motion_units(self._scale)
        return 1

    def update_board(
        self, motion: StepResult | None = None, progress: float = 1.0
    ) -> None:
        """Snapshot the game and repaint only the cells that changed.

        With `motion`, the step just taken is drawn `progress` of the way done.
        """
        partial: dict[Position, PartialCell] = {}
        if (
            motion is not None
            and motion.head is not None
            and motion.heading is not None
            and self.motion_units() > 1
        ):
            partial = motion_cells(
                motion.head,
                motion.heading,
                motion.vacated,
                motion.vacated_heading,
                progress,
                self._scale,
            )
        state = BoardState.capture(_snake_app(self).game, partial)
        drawn, self._drawn = self._drawn, state
        if drawn is None or (state.width, state.height) != (drawn.width, drawn.height):
            super().refresh()
            return
        changed = set(drawn.snake ^ state.snake)
        if (drawn.food, drawn.world, drawn.food_symbol) != (
            state.food,
            state.world,
            state.food_symbol,
        ):
            changed.update((drawn.food, state.food))
        changed.update(
            cell
            for cell in drawn.partial.keys() | state.partial.keys()
            if drawn.partial.get(cell) != state.partial.get(cell)
        )
        if changed:
            geometry = self._geometry(state)
            super().refresh(*(self._cell_region(geometry, cell) for cell in changed))

    def _state(self) -> BoardState:
        """The snapshot to draw, taking one if a full refresh cleared it."""
        if self._drawn is None:
            self._drawn = BoardState.capture(_snake_app(self).game)
        return self._drawn

    def _geometry(self, state: BoardState) -> BoardGeometry:
        """Centre the board, framed when capped or walled, with room to spare.

        "fill" mode covers the terminal edge-to-edge, so a wrapping board has no
        margin to frame. The frame makes the capped board's boundary (and the
        wrap-around) visible inside the letterbox margin. With walls the frame
        is the wall, so the layout leaves room for it in either mode.
        """
        width, height = self.size
        config = _snake_app(self).config
        board_cols = CELL_BASE_WIDTH * state.width * self._scale
        board_rows = state.height * self._scale
        framed = (
            (config.sizing_mode == "cap" or config.walls)
            and width >= board_cols + FRAME_MARGIN
            and height >= board_rows + FRAME_MARGIN
        )
        block_cols = board_cols + FRAME_MARGIN * framed
        block_rows = board_rows + FRAME_MARGIN * framed
        return BoardGeometry(
            left=max(0, (width - block_cols) // 2),
            top=max(0, (height - block_rows) // 2),
            board_cols=board_cols,
            board_rows=board_rows,
            framed=framed,
        )

    def _cell_region(self, geometry: BoardGeometry, cell: Position) -> Region:
        """The widget region one logical cell occupies."""
        x, y = cell
        cell_cols = CELL_BASE_WIDTH * self._scale
        return Region(
            geometry.board_left + x * cell_cols,
            geometry.board_top + y * self._scale,
            cell_cols,
            self._scale,
        )

    @override
    def render_line(self, y: int) -> Strip:
        """Render one terminal row: margin, frame edge or board row, margin."""
        width = self.size.width
        base_style = self.visual_style.rich_style
        if self._needed is not None:
            return self._too_small_line(y, self._needed)
        walls = _snake_app(self).config.walls
        state = self._state()
        geometry = self._geometry(state)
        row = y - geometry.board_top
        segments: list[Segment]
        if 0 <= row < geometry.board_rows:
            logical_y, sub_row = divmod(row, self._scale)
            line = self._board_rows(state, logical_y)[sub_row]
            if geometry.framed:
                side = frame_side(walls=walls)
                segments = [side, *line, side]
            else:
                segments = line
        elif geometry.framed and row in (-1, geometry.board_rows):
            segments = [frame_rule(geometry.board_cols, top=row == -1, walls=walls)]
        else:
            return Strip.blank(width, base_style)
        strip = Strip([Segment(" " * geometry.left), *segments])
        return strip.apply_style(base_style).adjust_cell_length(width, base_style)

    def _too_small_line(self, y: int, needed: tuple[int, int]) -> Strip:
        """One row of the centred "terminal too small" message.

        Each paragraph is wrapped to the view, which is narrow exactly when the
        terminal is small.
        """
        size = self.app.size
        paragraphs = [
            "Terminal too small for food sprites",
            f"Needs {needed[0]} x {needed[1]}; this is {size.width} x {size.height}.",
            "Enlarge the window or turn sprites off.",
            "ESC main menu · Q quit",
        ]
        width = self.size.width
        lines: list[str] = []
        for paragraph in paragraphs:
            lines.extend([*textwrap.wrap(paragraph, max(1, width - 2)), ""])
        lines.pop()
        base_style = self.visual_style.rich_style
        index = y - (self.size.height - len(lines)) // 2
        if not 0 <= index < len(lines):
            return Strip.blank(width, base_style)
        text = lines[index]
        left = max(0, (width - cell_len(text)) // 2)
        strip = Strip([Segment(" " * left + text)])
        return strip.apply_style(base_style).adjust_cell_length(width, base_style)

    def _board_rows(self, state: BoardState, logical_y: int) -> list[list[Segment]]:
        """The `scale` terminal rows that draw one logical row of `state`.

        Built once per snapshot and scale, so the lines of one logical row share
        a single render.
        """
        rows_for = self._rows_for
        if (
            self._rows is None
            or rows_for is None
            or rows_for[0] is not state
            or rows_for[1] != self._scale
        ):
            self._rows_for = (state, self._scale)
            self._rows = {}
        rows = self._rows.get(logical_y)
        if rows is None:
            rows = self._rows[logical_y] = self._render_board_rows(state, logical_y)
        return rows

    def _render_board_rows(
        self, state: BoardState, logical_y: int
    ) -> list[list[Segment]]:
        """Render one logical row of `state` (see `_board_rows`)."""
        config = _snake_app(self).config
        return render_board_row(
            state.width,
            logical_y,
            state.snake,
            state.food,
            self._scale,
            config.snake_block,
            config.empty_cell,
            self._food_tile(state),
            state.partial,
        )

    def _food_tile(self, state: BoardState) -> list[list[Segment]]:
        """Pick the food rendering: the pixel sprite if enabled, else the glyph.

        With sprites on the scale never drops below `config.MIN_SPRITE_SCALE`, so
        the food style never depends on the terminal size.
        """
        config = _snake_app(self).config
        if config.uses_sprites:
            return sprites.food_tile(sprites.get_food_sprite(state.world), self._scale)
        return glyph_food_tile(state.food_symbol, config.empty_cell, self._scale)


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
