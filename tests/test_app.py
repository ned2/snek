"""Integration tests for the Snek app."""

import asyncio
from dataclasses import replace

import pytest
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Label, Static
from textual.worker import WorkerCancelled

from snek import clipboard
from snek.app import SnakeApp
from snek.config import GameConfig, default_config
from snek.figlet import FigletText
from snek.game_rules import Direction
from snek.modes import apply_mode
from snek.screens import (
    DiagnosticsModal,
    GameOverModal,
    GameScreen,
    SettingsModal,
    SidePanel,
    SnakeView,
    SplashScreen,
    StatDisplay,
)
from snek.settings import ROWS, widest_help

# Sprites on the 36x20 cap, up to scale 3, wrapping: needs 174x40 at scale 2.
SPRITES = GameConfig(food_sprites=True, cell_scale=3, walls=False)


def _arm_self_collision(game) -> None:
    """Park a snake that self-collides on its next (UP) step, food out of the way."""
    game.set_snake_position([(5, 5), (4, 5), (4, 4), (5, 4), (6, 4)])
    game.direction = Direction.UP
    game.set_food_position((0, 0))


def _serpentine_cycle(width: int, height: int) -> list[tuple[int, int]]:
    """Return a toroidal Hamiltonian cycle for an even-height test board."""
    assert height % 2 == 0
    return [
        (x, y)
        for y in range(height)
        for x in (range(width) if y % 2 == 0 else range(width - 1, -1, -1))
    ]


def _assert_game_invariants(game) -> None:
    """Assert the coordinate invariants that viewport changes must preserve."""
    assert len(game.snake) == len(set(game.snake))
    assert all(0 <= x < game.width and 0 <= y < game.height for x, y in game.snake)
    for first, second in zip(game.snake, game.snake[1:], strict=False):
        dx = min(abs(first[0] - second[0]), game.width - abs(first[0] - second[0]))
        dy = min(abs(first[1] - second[1]), game.height - abs(first[1] - second[1]))
        assert dx + dy == 1
    assert 0 <= game.food[0] < game.width
    assert 0 <= game.food[1] < game.height
    assert game.food not in game.snake


def _assert_fully_in_view(widget: Static, width: int, height: int) -> None:
    """Assert a displayed widget has non-empty geometry inside the terminal."""
    assert widget.display
    assert widget.region.width > 0
    assert widget.region.height > 0
    assert widget.region.x >= 0
    assert widget.region.y >= 0
    assert widget.region.right <= width
    assert widget.region.bottom <= height


def _assert_horizontally_centred(widget: Static, width: int) -> None:
    """Assert a widget's region sits centred (to within a cell) across the terminal."""
    left_gap = widget.region.x
    right_gap = width - widget.region.right
    assert abs(left_gap - right_gap) <= 1, (left_gap, right_gap)


def _death_message(app) -> str:
    """The rendered text of the game-over modal's banner line."""
    return str(app.screen.query_one(".death-message", Static).render())


def _foods_line(app) -> str:
    """The rendered 'Foods collected: N' line on the game-over modal."""
    for static in app.screen.query(Static):
        try:
            text = str(static.render())
        except Exception:
            continue
        if "Foods collected" in text:
            return text
    return ""


@pytest.mark.asyncio
async def test_app_startup():
    """Test app starts with splash screen."""
    app = SnakeApp()
    async with app.run_test():
        # Should show splash screen as the current screen
        assert isinstance(app.screen, SplashScreen)


@pytest.mark.asyncio
async def test_splash_is_fully_usable_at_80_by_24() -> None:
    """The supported minimum shows compact branding and every essential action."""
    app = SnakeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SplashScreen)

        large_title = screen.query_one("#splash-title", FigletText)
        compact_title = screen.query_one("#splash-title-compact", FigletText)
        start_prompt = screen.query_one("#splash-start-prompt", Static)
        controls_prompt = screen.query_one("#splash-controls-prompt", Static)
        version = screen.query_one("#splash-version", Static)
        mode = screen.query_one("#splash-mode", Static)
        mode_help = screen.query_one("#splash-mode-help", Static)

        assert not large_title.display
        assert compact_title.display
        assert large_title._timer is None
        assert compact_title._timer is None
        for widget in (
            compact_title,
            mode,
            mode_help,
            start_prompt,
            controls_prompt,
            version,
        ):
            _assert_fully_in_view(widget, 80, 24)
        _assert_horizontally_centred(compact_title, 80)

        assert compact_title.region.height == len(compact_title._lines) == 5
        # Too wide for 80 columns, the start prompt splits into two balanced lines.
        assert start_prompt.region.height == 2
        assert controls_prompt.region.height == 1
        assert str(start_prompt.render()).splitlines() == [
            "Press SPACE to start, D to run the demo,",
            "←/→ to change mode, or S for detailed settings.",
        ]
        assert str(controls_prompt.render()) == (
            "Gameplay: use arrow or WASD keys to move, Space to pause, Q to quit."
        )
        assert controls_prompt.styles.text_style.italic


@pytest.mark.asyncio
async def test_splash_retains_large_title_at_120_by_40() -> None:
    """A roomy viewport keeps the original large-title visual hierarchy."""
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SplashScreen)

        large_title = screen.query_one("#splash-title", FigletText)
        compact_title = screen.query_one("#splash-title-compact", FigletText)
        assert large_title.display
        assert not compact_title.display
        _assert_fully_in_view(large_title, 120, 40)
        _assert_horizontally_centred(large_title, 120)
        _assert_fully_in_view(screen.query_one("#splash-start-prompt"), 120, 40)
        _assert_fully_in_view(screen.query_one("#splash-controls-prompt"), 120, 40)
        _assert_fully_in_view(screen.query_one("#splash-version"), 120, 40)
        _assert_fully_in_view(screen.query_one("#splash-mode"), 120, 40)
        assert large_title.region.height == len(large_title._lines) == 25


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("animation_level", "expected"),
    [("none", False), ("basic", False), ("full", True)],
)
async def test_splash_animation_respects_preference(
    animation_level: str, expected: bool
) -> None:
    """Continuous splash decoration runs only at Textual's full animation level."""
    app = SnakeApp()
    app.animation_level = animation_level
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        title = app.screen.query_one("#splash-title", FigletText)
        assert title._animation_enabled is expected
        assert (title._timer is not None) is expected


@pytest.mark.asyncio
async def test_start_game_from_splash():
    """Test starting game from splash screen."""
    app = SnakeApp()
    async with app.run_test() as pilot:
        # Press Enter to start
        await pilot.press("space")
        await pilot.pause()

        # Should now be on game screen
        assert isinstance(app.screen, GameScreen)

        # Game should be initialized on the app
        assert app.game is not None
        assert app.screen.query_one(SnakeView) is not None
        assert app.screen.query_one(SidePanel) is not None


@pytest.mark.asyncio
async def test_game_controls():
    """Test game controls work correctly."""
    app = SnakeApp()
    async with app.run_test() as pilot:
        # Start game
        await pilot.press("space")
        await pilot.pause()

        # Get the game from the app
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        game = app.game

        # Stop the auto-timer so only our explicit ticks advance the model; the
        # 0.1s interval would otherwise drain the turn buffer between key presses.
        game_screen._disarm()

        # Park a length-1 snake with food out of the way so each step is a plain
        # move and never ends the game while we exercise the controls.
        game.set_snake_position([(5, 5)])
        game.set_food_position((0, 0))
        game.direction = Direction.RIGHT

        # A key press buffers a turn; the committed heading updates on the step.
        await pilot.press("up")
        game_screen.tick()
        assert game.direction == Direction.UP

        await pilot.press("left")
        game_screen.tick()
        assert game.direction == Direction.LEFT

        # Two opposing turns within one tick can't reverse the snake: heading
        # RIGHT, an immediate UP+LEFT applies UP now and defers LEFT, rather than
        # stepping straight back onto the body.
        game.set_snake_position([(5, 5), (4, 5), (3, 5)])
        game.direction = Direction.RIGHT
        await pilot.press("up")
        await pilot.press("left")
        game_screen.tick()
        assert game.direction == Direction.UP
        assert game.game_over is False


@pytest.mark.asyncio
async def test_pause_functionality():
    """Test pause/unpause functionality."""
    app = SnakeApp()
    async with app.run_test() as pilot:
        # Start game
        await pilot.press("space")
        await pilot.pause()

        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)

        # Pause game
        await pilot.press("space")
        await pilot.pause()
        assert app.game.paused is True

        # Should now have a pause modal on the screen stack
        # The pause modal should be the top screen
        from snek.screens import PauseModal

        # Check if we can find a PauseModal in the screen stack
        pause_modal_found = any(
            isinstance(screen, PauseModal) for screen in app.screen_stack
        )
        assert pause_modal_found

        # Unpause by pressing space
        await pilot.press("space")
        await pilot.pause()
        assert app.game.paused is False


class _RecordedTimer:
    """Stands in for a loop timer: records its delay and whether it was stopped."""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def _record_loop_timers(monkeypatch, game_screen) -> list[_RecordedTimer]:
    """Replace the screen's timer factories so each scheduled wake is recorded."""
    armed: list[_RecordedTimer] = []

    def set_timer(delay: float, callback, **kwargs) -> _RecordedTimer:
        timer = _RecordedTimer(delay)
        armed.append(timer)
        return timer

    def set_interval(*args, **kwargs):
        raise AssertionError("the loop only schedules one-shot wakes")

    monkeypatch.setattr(game_screen, "set_timer", set_timer)
    monkeypatch.setattr(game_screen, "set_interval", set_interval)
    return armed


@pytest.mark.asyncio
async def test_loop_wakes_exactly_at_step_deadlines(monkeypatch) -> None:
    """The loop sleeps until each step is due, keeps waited time across a pause,
    re-reads the interval after eating, and stops for good at game over."""
    now = [0.0]
    # A binary-exact interval keeps the fake-clock arithmetic exact. Without
    # interpolation the loop wakes only at step deadlines.
    app = SnakeApp(GameConfig(initial_speed_interval=0.125, smooth_motion=False))
    async with app.run_test() as pilot:
        await pilot.press("space")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        game_screen._now = lambda: now[0]
        armed = _record_loop_timers(monkeypatch, game_screen)
        game = app.game
        game.set_snake_position([(5, 5)])
        game.set_food_position((0, 0))
        game.direction = Direction.RIGHT
        game_screen._restart_loop()
        interval = game.current_interval
        assert [timer.delay for timer in armed] == [interval]

        def wake_at(t: float) -> None:
            now[0] = t
            game_screen._on_frame()

        # The wake at the deadline steps and sleeps a full interval again.
        wake_at(0.125)
        assert game.snake[0] == (6, 5)
        assert armed[-1].delay == pytest.approx(interval)
        # A stray early wake doesn't step; it sleeps only for the remainder.
        wake_at(0.1875)
        assert game.snake[0] == (6, 5)
        assert armed[-1].delay == pytest.approx(0.0625)

        # Pausing keeps the time already waited and discards the paused time.
        now[0] = 0.21875
        game_screen.action_pause()
        await pilot.pause()
        assert game_screen.timer is None
        assert armed[-1].stopped
        now[0] = 100.0
        await pilot.press("space")
        await pilot.pause()
        assert not game.paused
        assert armed[-1].delay == pytest.approx(0.03125)
        wake_at(100.03125)
        assert game.snake[0] == (7, 5)

        # Eating speeds up the very next step.
        game.set_food_position((8, 5))
        wake_at(100.03125 + interval)
        assert game.symbols_consumed == 1
        assert game.current_interval < interval
        assert armed[-1].delay == pytest.approx(game.current_interval)

        # Game over stops the loop, and a stale wake schedules nothing more.
        _arm_self_collision(game)
        wake_at(200.0)
        await pilot.pause()
        assert isinstance(app.screen, GameOverModal)
        assert game_screen.timer is None
        count = len(armed)
        game_screen._on_frame()
        assert len(armed) == count


@pytest.mark.asyncio
async def test_stale_queued_wakes_are_ignored() -> None:
    """A wake queued by a timer that was since stopped or replaced does nothing.

    Textual queues timer callbacks on the screen, so stopping a timer that has
    already fired cannot recall its wake; the loop must ignore it itself.
    """
    app = SnakeApp()
    async with app.run_test() as pilot:
        await pilot.press("space")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        stale = game_screen._generation
        game_screen._disarm()
        head = app.game.snake[0]
        game_screen._last_frame = -100.0  # A real wake would now be long overdue.
        game_screen._on_wake(stale)
        assert app.game.snake[0] == head
        assert game_screen.timer is None


@pytest.mark.asyncio
async def test_interpolated_steps_slide_on_substep_wakes(monkeypatch) -> None:
    """While interpolating, the loop wakes at each substep and the board shows
    the step part done; fast, late or final steps are drawn whole."""
    now = [0.0]
    app = SnakeApp(GameConfig(initial_speed_interval=0.125))
    async with app.run_test() as pilot:
        await pilot.press("space")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        view = game_screen.query_one(SnakeView)
        units = view.motion_units()
        assert units > 1
        game_screen._now = lambda: now[0]
        armed = _record_loop_timers(monkeypatch, game_screen)
        game = app.game
        game.set_snake_position([(5, 5)])
        game.set_food_position((0, 0))
        game.direction = Direction.RIGHT
        game_screen._restart_loop()
        view.refresh()
        substep = game.current_interval / units
        assert armed[-1].delay == pytest.approx(substep)

        def wake_at(t: float) -> None:
            now[0] = t
            game_screen._on_frame()

        # The step shows its first increment at once: the head starts entering
        # its new cell as the vacated one starts draining.
        wake_at(0.125)
        assert game.snake[0] == (6, 5)
        assert view._drawn is not None
        assert view._drawn.partial == {
            (6, 5): (Direction.LEFT, 1),
            (5, 5): (Direction.RIGHT, units - 1),
        }
        assert armed[-1].delay == pytest.approx(substep)
        # By the last substep the step is drawn whole.
        wake_at(0.125 + (units - 1) * substep)
        assert view._drawn.partial == {}
        assert armed[-1].delay == pytest.approx(substep)

        # A late wake that runs two steps at once draws them whole.
        wake_at(0.125 + 3 * game.current_interval)
        assert game.snake[0] == (8, 5)
        assert view._drawn.partial == {}

        # Steps shorter than two frames are drawn whole, waking at deadlines.
        game.current_interval = 0.03125
        wake_at(now[0] + 0.03125)
        assert view._drawn.partial == {}
        assert armed[-1].delay == pytest.approx(0.03125)

        # Game over settles the board whole.
        game.current_interval = 0.125
        wake_at(now[0] + 0.125)
        assert view._drawn.partial != {}
        _arm_self_collision(game)
        wake_at(now[0] + 0.125)
        await pilot.pause()
        assert isinstance(app.screen, GameOverModal)
        assert view._drawn is not None
        assert view._drawn.partial == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(80, 24), (200, 50)])
async def test_interpolated_updates_match_a_full_render(monkeypatch, size) -> None:
    """Every substep repaints exactly the cells whose drawing changed.

    Demo play covers turns, wraps and eating. After each wake, Textual's cached
    lines must equal a fresh render of the same snapshot; a missed cell would
    survive as a stale cached line.
    """
    now = [0.0]
    app = SnakeApp()
    async with app.run_test(size=size) as pilot:
        await pilot.press("d")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        view = game_screen.query_one(SnakeView)
        assert view.motion_units() > 1
        game_screen._now = lambda: now[0]
        armed = _record_loop_timers(monkeypatch, game_screen)
        game = app.game
        game_screen._restart_loop()
        eaten = game.symbols_consumed
        partial_wakes = 0
        for _ in range(600):
            # Keep food close so the run covers eating, growth and food moves.
            head_x, head_y = game.snake[0]
            if game.symbols_consumed == eaten and game.food[1] != head_y:
                game.set_food_position(((head_x + 4) % game.width, head_y))
            now[0] += armed[-1].delay
            game_screen._on_frame()
            if game.game_over:
                break
            assert view._drawn is not None
            partial_wakes += bool(view._drawn.partial)
            cached = [strip.text for strip in view.render_lines(view.size.region)]
            fresh = [view.render_line(y).text for y in range(view.size.height)]
            assert cached == fresh
        assert game.symbols_consumed > eaten
        assert partial_wakes > 0


@pytest.mark.asyncio
async def test_game_actions_tolerate_timer_teardown() -> None:
    """Lifecycle actions remain safe after Textual has cleared the timer."""
    app = SnakeApp()
    async with app.run_test() as pilot:
        await pilot.press("space")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        assert game_screen.timer is not None
        game_screen.timer.stop()
        game_screen.timer = None

        game_screen.action_pause()
        await pilot.pause()
        assert app.game.paused
        await pilot.press("space")
        await pilot.pause()
        assert not app.game.paused

        game_screen.action_diagnostics()
        await pilot.pause()
        assert isinstance(app.screen, DiagnosticsModal)
        await pilot.press("space")
        await pilot.pause()

        _arm_self_collision(app.game)
        game_screen.tick()
        await pilot.pause()
        assert isinstance(app.screen, GameOverModal)


@pytest.mark.asyncio
async def test_game_over_and_restart():
    """Test game over screen and restart functionality."""
    app = SnakeApp()
    async with app.run_test() as pilot:
        # Start game
        await pilot.press("space")
        await pilot.pause()

        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)

        # Force game over
        app.game.game_over = True

        # Manually trigger the game over modal
        from snek.screens import GameOverModal

        app.push_screen(GameOverModal())
        await pilot.pause()

        # Should now have a game over modal
        game_over_modal_found = any(
            isinstance(screen, GameOverModal) for screen in app.screen_stack
        )
        assert game_over_modal_found

        # Get the modal and verify it has the restart action
        modal = app.screen
        assert isinstance(modal, GameOverModal)
        assert hasattr(modal, "action_restart")

        # Get the GameScreen and verify it has restart_game method
        game_screen_in_stack = None
        for screen in app.screen_stack:
            if isinstance(screen, GameScreen):
                game_screen_in_stack = screen
                break
        assert game_screen_in_stack is not None
        assert hasattr(game_screen_in_stack, "restart_game")

        # Test restart_game method directly
        app.game.symbols_consumed = 5  # Change state
        game_screen_in_stack.restart_game()
        assert app.game.symbols_consumed == 0  # Should be reset
        assert not app.game.game_over  # Should not be game over
        assert len(app.game.snake) == 1  # Should have initial snake length


@pytest.mark.asyncio
async def test_restart_returns_to_playable_game():
    """SPACE on the game-over modal restarts and lands back on the GAME screen.

    Regression: `action_restart` used to pop twice, dropping through to the splash
    while the restarted game ticked on invisibly underneath.
    """
    app = SnakeApp()
    async with app.run_test() as pilot:
        await pilot.press("space")
        await pilot.pause()

        # Real death via a self-colliding snake (so tick() pushes the modal).
        app.game.symbols_consumed = 9
        _arm_self_collision(app.game)
        app.screen.tick()
        await pilot.pause()
        assert isinstance(app.screen, GameOverModal)

        # SPACE -> restart: back on the game screen with a fresh, live game.
        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        assert app.game.game_over is False
        assert app.game.symbols_consumed == 0
        assert len(app.game.snake) == 1
        head = app.game.snake[0]
        app.screen.tick()
        assert app.game.snake[0] != head  # not frozen


@pytest.mark.asyncio
async def test_new_game_from_menu_resets_and_plays():
    """Starting a game from the splash after a finished game starts clean.

    `GameScreen` and `Game` are reused singletons, so without an explicit reset the
    second game would inherit the previous game's `game_over`/`won`/score and the
    board would freeze (`Game.step` early-returns while `game_over`).
    """
    app = SnakeApp()
    async with app.run_test() as pilot:
        await pilot.press("space")
        await pilot.pause()
        game_screen = app.screen

        # Finish game 1 as a WIN with a stale score, show the modal.
        app.game.won = True
        app.game.game_over = True
        app.game.symbols_consumed = 42
        game_screen._disarm()
        app.push_screen(GameOverModal())
        await pilot.pause()

        # ENTER -> main menu, then D -> a fresh demo game.
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, SplashScreen)
        await pilot.press("d")
        await pilot.pause()

        assert isinstance(app.screen, GameScreen)
        assert app.game.game_over is False
        assert app.game.won is False
        assert app.game.symbols_consumed == 0
        assert len(app.game.snake) == 1
        assert app.screen.demo_ai is not None
        head = app.game.snake[0]
        app.screen.tick()
        assert app.game.snake[0] != head  # live, not frozen


@pytest.mark.asyncio
async def test_game_over_banner_reflects_current_game():
    """The win/death banner and food count always reflect the game that ended.

    `GameOverModal` is pushed as a fresh instance each game-over, so a death after
    a prior win never shows a stale "you win" banner or a stale score.
    """
    app = SnakeApp()
    async with app.run_test() as pilot:
        await pilot.press("space")
        await pilot.pause()
        game_screen = app.screen

        # Game 1: a WIN.
        app.game.won = True
        app.game.game_over = True
        app.game.symbols_consumed = 99
        game_screen._disarm()
        app.push_screen(GameOverModal())
        await pilot.pause()
        assert "BOARD FILLED" in _death_message(app)
        assert "99" in _foods_line(app)

        # Restart, then die a normal death.
        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        assert app.game.won is False
        app.game.symbols_consumed = 4
        _arm_self_collision(app.game)
        app.screen.tick()
        await pilot.pause()

        assert isinstance(app.screen, GameOverModal)
        assert "SNEK DED" in _death_message(app)
        assert "BOARD FILLED" not in _death_message(app)
        assert "4" in _foods_line(app)  # current score, not the stale 99


@pytest.mark.asyncio
async def test_quit_from_game():
    """Test quitting from game exits the app."""
    app = SnakeApp()
    async with app.run_test() as pilot:
        # Start game
        await pilot.press("space")
        await pilot.pause()

        # Quit should exit the app entirely
        await pilot.press("q")
        await pilot.pause()

        # App should have exited (the test will complete successfully if app.exit() was called)
        # If the app didn't exit, we'd still be in the game screen, which we can verify
        # by checking that the app is no longer running
        assert not app.is_running


@pytest.mark.asyncio
async def test_stats_panel_updates():
    """Stats panel labels update from game state through the data binding."""
    app = SnakeApp()
    async with app.run_test() as pilot:
        # Start game
        await pilot.press("space")
        await pilot.pause()

        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        game = app.game

        displays = {d._label: d for d in game_screen.query(StatDisplay)}

        def value_label(label: str) -> str:
            """The text actually rendered in a stat's value cell."""
            return str(displays[label].query_one(".stat-value", Label).content)

        # Initial state is pushed to the panel by on_mount -> _sync_reactives.
        assert displays["Total foods"].value == "0"
        assert value_label("Total foods") == "0"
        assert value_label("Progress") == "0/10"
        assert value_label("World") == "Basic Symbols"

        # Eat one food: tick() advances the model and calls _sync_reactives(),
        # whose GameScreen reactives propagate to the StatDisplays via data_bind.
        head_x, head_y = game.snake[0]
        game.direction = Direction.RIGHT
        game.set_food_position((head_x + 1, head_y))
        game_screen.tick()
        await pilot.pause()

        assert game.symbols_consumed == 1
        assert displays["Total foods"].value == "1"
        assert value_label("Total foods") == "1"
        assert value_label("Progress") == "1/10"

        # A world jump re-formats the World label through the same binding.
        game.current_world = 1
        game_screen._sync_reactives()
        await pilot.pause()
        assert value_label("World") == "Ancient Egypt"


@pytest.mark.asyncio
async def test_theme_changes_with_world():
    """Test theme changes when world changes."""
    config = GameConfig()
    app = SnakeApp(config=config)

    async with app.run_test() as pilot:
        # Start game
        await pilot.press("space")
        await pilot.pause()

        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        game = app.game

        # Store initial theme and old world for comparison
        initial_theme = app.theme
        old_world = game.current_world

        game_screen._disarm()
        head_x, head_y = game.snake[0]
        game.direction = Direction.RIGHT
        game.set_food_position(((head_x + 1) % game.width, head_y))
        game.symbols_consumed = config.symbols_per_world - 1
        game.symbols_in_current_world = config.symbols_per_world - 1
        game_screen.tick()
        await pilot.pause()

        # World should have changed
        assert game.current_world == old_world + 1

        # Theme should have changed (world 1 has 'snek-ocean' theme)
        assert app.theme != initial_theme
        assert app.theme == "snek-ocean"


@pytest.mark.asyncio
async def test_resize_handling():
    """Repeated viewport changes preserve a live, nearly-full game exactly."""
    app = SnakeApp()
    async with app.run_test(size=(120, 32)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        game_screen._disarm()

        game = app.game
        cycle = _serpentine_cycle(game.width, game.height)
        game.set_snake_position(cycle[:-1])
        game.set_food_position(cycle[-1])  # exactly one free cell remains
        game.direction = Direction.RIGHT
        game.turn(Direction.UP)
        game.symbols_consumed = 37
        before = (
            game.width,
            game.height,
            list(game.snake),
            game.food,
            list(game._pending_turns),
            game.symbols_consumed,
        )
        _assert_game_invariants(game)

        # Shrink, grow, become too small even for scale one, then return. None of
        # these viewport-only events may rewrite model state.
        for size in ((80, 24), (280, 70), (30, 8), (120, 32)):
            await pilot.resize_terminal(*size)
            await pilot.pause()
            assert (
                game.width,
                game.height,
                game.snake,
                game.food,
                game._pending_turns,
                game.symbols_consumed,
            ) == before
            _assert_game_invariants(game)


@pytest.mark.asyncio
async def test_resize_preserves_stateful_demo_strategy():
    """A live demo keeps its strategy instance and cached topology on resize."""
    app = SnakeApp(demo_strategy="hamiltonian")
    async with app.run_test(size=(120, 32)) as pilot:
        await pilot.press("d")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        game_screen._disarm()
        strategy = game_screen.demo_ai
        assert strategy is not None
        strategy.get_next_direction()
        built_for = strategy._built_for
        cycle = list(strategy.cycle)

        await pilot.resize_terminal(280, 70)
        await pilot.pause()

        assert game_screen.demo_ai is strategy
        assert strategy._built_for == built_for
        assert strategy.cycle == cycle


@pytest.mark.asyncio
async def test_logical_grid_reaches_cap_at_scale_one():
    """A terminal just big enough lands on the cap and still draws at scale 1."""
    app = SnakeApp()
    async with app.run_test(size=(120, 32)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        cfg = app.config
        assert (app.game.width, app.game.height) == (
            cfg.max_grid_width,
            cfg.max_grid_height,
        )
        assert app.screen.query_one(SnakeView)._scale == 1


@pytest.mark.asyncio
async def test_grid_shrinks_below_cap_on_small_terminal():
    """A terminal too small for the cap gets a smaller (clamped) board."""
    app = SnakeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        cfg = app.config
        # 80 cols can't fit the cap's width at scale 1, so it shrinks.
        assert app.game.width < cfg.max_grid_width
        assert app.screen.query_one(SnakeView)._scale == 1


@pytest.mark.asyncio
async def test_board_scales_up_but_grid_stays_capped_on_large_terminal():
    """A large terminal keeps the capped logical grid but scales cells up."""
    app = SnakeApp(config=GameConfig(cell_scale=3))
    async with app.run_test(size=(220, 70)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        cfg = app.config
        # Logical grid is still the cap — difficulty doesn't grow with the window.
        assert (app.game.width, app.game.height) == (
            cfg.max_grid_width,
            cfg.max_grid_height,
        )
        # ...but cells are drawn larger, never past the cap.
        scale = app.screen.query_one(SnakeView)._scale
        assert 1 < scale <= cfg.cell_scale


@pytest.mark.asyncio
async def test_fill_mode_grows_grid_to_fill_terminal():
    """'fill' mode grows the logical grid past the cap and keeps the fixed scale."""
    app = SnakeApp(config=GameConfig(sizing_mode="fill", cell_scale=1, walls=False))
    async with app.run_test(size=(172, 48)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        snake_view = app.screen.query_one(SnakeView)
        # At scale 1 the grid fills the view (~width/2 cells), well past the cap.
        assert app.game.width > app.config.max_grid_width
        assert app.game.width == snake_view.size.width // 2
        assert snake_view._scale == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("sizing_mode", ["cap", "fill"])
async def test_walls_are_always_drawn(sizing_mode):
    """With walls the heavy frame is part of the game, so the layout leaves room
    for it even in 'fill' mode, which otherwise covers the view edge to edge."""
    config = GameConfig(sizing_mode=sizing_mode, cell_scale=1, walls=True)
    app = SnakeApp(config=config)
    async with app.run_test(size=(172, 48)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        view = app.screen.query_one(SnakeView)
        lines = _board_text(view).split("\n")
        top = next(i for i, line in enumerate(lines) if "┏" in line)
        bottom = next(i for i, line in enumerate(lines) if "┗" in line)
        board_cols = 2 * app.game.width
        assert lines[top].strip() == "┏" + "━" * board_cols + "┓"
        assert bottom - top - 1 == app.game.height
        assert all(
            line.strip().startswith("┃") and line.strip().endswith("┃")
            for line in lines[top + 1 : bottom]
        )
        if sizing_mode == "fill":
            assert app.game.width == (view.size.width - 2) // 2


def _board_text(snake_view) -> str:
    """Re-snapshot the live game and flatten every rendered line to plain text."""
    snake_view.refresh()
    return "\n".join(
        snake_view.render_line(y).text for y in range(snake_view.size.height)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(80, 24), (200, 50)])
async def test_partial_board_updates_match_a_full_render(size) -> None:
    """Cell-level repaints leave the screen identical to redrawing everything.

    Each step repaints only the cells that changed, and Textual keeps every
    other line cached. A missed cell would survive here as a stale cached line.
    """
    app = SnakeApp()
    async with app.run_test(size=size) as pilot:
        await pilot.press("d")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        assert game_screen.timer is not None
        game_screen._disarm()
        view = game_screen.query_one(SnakeView)
        game = app.game
        eaten = game.symbols_consumed
        for _ in range(60):
            # Keep food close so the run covers eating, growth and food moves.
            head_x, head_y = game.snake[0]
            if game.symbols_consumed == eaten and game.food[1] != head_y:
                game.set_food_position(((head_x + 4) % game.width, head_y))
            game_screen.tick()
            await pilot.pause()
            if game.game_over:
                break
        assert game.symbols_consumed > eaten

        cached = [strip.text for strip in view.render_lines(view.size.region)]
        view.refresh()
        fresh = [strip.text for strip in view.render_lines(view.size.region)]
        assert cached == fresh


@pytest.mark.asyncio
async def test_food_uses_glyph_at_scale_one():
    """On a small terminal (scale 1) food is the themed glyph, not a sprite."""
    app = SnakeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        app.screen._disarm()
        game = app.game
        game.reset()
        hx, hy = game.snake[0]
        game.set_food_position((hx + 3, hy))
        text = _board_text(app.screen.query_one(SnakeView))
        assert game.food_symbol in text  # glyph drawn
        assert "▄" not in text  # no sprite pixels


@pytest.mark.asyncio
async def test_food_uses_sprite_at_large_scale():
    """With sprites on, food is drawn as a pixel sprite."""
    app = SnakeApp(config=SPRITES)
    async with app.run_test(size=(280, 70)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        app.screen._disarm()
        game = app.game
        game.reset()
        hx, hy = game.snake[0]
        game.set_food_position((hx + 3, hy))
        snake_view = app.screen.query_one(SnakeView)
        assert snake_view._scale >= 2
        text = _board_text(snake_view)
        assert "▄" in text  # sprite pixels drawn
        assert game.food_symbol not in text  # glyph replaced


@pytest.mark.asyncio
async def test_food_sprites_can_be_disabled():
    """With food_sprites off, even a large terminal keeps the glyph."""
    app = SnakeApp(config=GameConfig(food_sprites=False))
    async with app.run_test(size=(280, 70)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        app.screen._disarm()
        game = app.game
        game.reset()
        hx, hy = game.snake[0]
        game.set_food_position((hx + 3, hy))
        text = _board_text(app.screen.query_one(SnakeView))
        assert game.food_symbol in text
        assert "▄" not in text


@pytest.mark.asyncio
async def test_sprites_hold_a_game_the_terminal_is_too_small_for():
    """Sprites never fall back to the glyph: a small terminal holds the game.

    The 36x20 cap needs 144x40 at scale two, so with the 30-column side panel a
    120x35 terminal must grow to 174x40.
    """
    app = SnakeApp(config=SPRITES)
    async with app.run_test(size=(120, 35)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        snake_view = game_screen.query_one(SnakeView)
        assert (app.game.width, app.game.height) == (36, 20)  # the whole cap
        assert snake_view.too_small
        assert game_screen.timer is None  # held, not running
        assert app.game.paused is False  # held is not paused
        text = _board_text(snake_view)
        assert "Terminal too small for food sprites" in text
        assert "Needs 174 x 40; this is 120 x 35." in text

        await pilot.resize_terminal(174, 40)
        await pilot.pause()
        assert not snake_view.too_small
        assert snake_view._scale == 2
        assert game_screen.timer is not None  # running again
        game_screen._disarm()
        game = app.game
        hx, hy = game.snake[0]
        game.set_food_position((hx + 3, hy))
        assert "▄" in _board_text(snake_view)  # the sprite, not the glyph


@pytest.mark.asyncio
async def test_sprites_hold_a_game_when_the_terminal_shrinks():
    """Shrinking mid-game holds the loop; it resumes without the held time."""
    app = SnakeApp(config=SPRITES)
    async with app.run_test(size=(200, 50)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        snake_view = game_screen.query_one(SnakeView)

        await pilot.resize_terminal(120, 35)
        await pilot.pause()
        assert snake_view.too_small
        assert snake_view._scale == 2  # never scale one with sprites
        assert game_screen.timer is None
        # Held: the snake stays put for longer than several steps.
        held = list(app.game.snake)
        await asyncio.sleep(3 * app.game.current_interval)
        await pilot.pause()
        assert app.game.snake == held

        await pilot.resize_terminal(200, 50)
        await pilot.pause()
        assert not snake_view.too_small
        assert game_screen.timer is not None


@pytest.mark.asyncio
async def test_escape_leaves_a_held_game_for_the_menu():
    """ESC reaches the menu (and so the settings) only while the game is held."""
    app = SnakeApp(config=SPRITES)
    async with app.run_test(size=(200, 50)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)  # not held: ESC does nothing

        await pilot.resize_terminal(120, 35)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, SplashScreen)

        # Turning sprites off lets the next game run in the same terminal.
        app.apply_settings(
            replace(app.settings, config=replace(app.config, food_sprites=False))
        )
        await pilot.press("space")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        assert not game_screen.query_one(SnakeView).too_small
        assert game_screen.timer is not None


@pytest.mark.asyncio
async def test_settings_refuse_sprites_at_scale_one_and_say_why() -> None:
    app = SnakeApp(config=GameConfig(food_sprites=True, cell_scale=2))
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("s")
        await pilot.pause()
        await pilot.press("down", "down", "down", "down", "down")  # cell scale
        await pilot.press("left")
        await pilot.pause()
        assert app.config.cell_scale == 2  # refused, and sprites left on
        assert app.config.food_sprites is True
        help_line = app.screen.query_one("#settings-help", Static)
        assert "Food sprites need a cell scale of at least 2" in str(help_line.render())
        assert help_line.has_class("-refused")

        await pilot.press("down")  # moving on restores the help line
        await pilot.pause()
        assert not help_line.has_class("-refused")


@pytest.mark.asyncio
async def test_scale_only_resize_does_not_rescale_snake():
    """Growing the terminal changes scale while leaving the fixed grid intact."""
    app = SnakeApp(config=GameConfig(cell_scale=3))
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        app.screen._disarm()
        snake_view = app.screen.query_one(SnakeView)
        scale_before = snake_view._scale
        before = list(app.game.snake)

        await pilot.resize_terminal(280, 70)
        await pilot.pause()

        assert (app.game.width, app.game.height) == (
            app.config.max_grid_width,
            app.config.max_grid_height,
        )
        assert snake_view._scale > scale_before  # the scale really did change
        assert app.game.snake == before  # ...but the snake was not rescaled


@pytest.mark.asyncio
async def test_diagnostics_opens_and_pauses_and_resumes():
    """`?` opens the diagnostics overlay and pauses; SPACE returns and resumes."""
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)

        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, DiagnosticsModal)
        assert app.game.paused is True

        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        assert app.game.paused is False


@pytest.mark.asyncio
async def test_diagnostics_scrolls_and_keeps_actions_reachable_at_80_by_24(
    monkeypatch,
):
    """The supported minimum can reach every row, copy, and close by keyboard."""
    monkeypatch.setattr("snek.clipboard._system_clipboard_command", lambda: None)
    app = SnakeApp(demo_strategy=f"strategy-{'x' * 160}")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, DiagnosticsModal)
        container = modal.query_one("#diagnostics-container", Vertical)
        title = modal.query_one("#diagnostics-title", FigletText)
        prompt = modal.query_one("#diagnostics-prompt", Static)
        scroll = modal.query_one("#diagnostics-scroll", VerticalScroll)
        params = modal.query_one("#diagnostics-params", Static)
        expected = modal._params_text()

        assert container.region.width <= 72
        assert container.region.height < 24
        for widget in (title, prompt, scroll):
            _assert_fully_in_view(widget, 80, 24)
        assert "C copy" in str(prompt.render())
        assert "SPACE close" in str(prompt.render())
        assert modal.focused is scroll
        assert scroll.max_scroll_y > 0

        # The deliberately long strategy value wraps onto extra display lines
        # instead of widening the body beyond its hidden horizontal overflow.
        assert params.virtual_size.height > len(expected.splitlines())
        assert scroll.max_scroll_x == 0

        await pilot.press("c")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.clipboard == expected

        await pilot.press("pagedown")
        await pilot.pause()
        assert scroll.scroll_y > 0
        await pilot.press("end")
        await pilot.pause()
        assert scroll.scroll_y == scroll.max_scroll_y

        # Dismissal remains bound at the modal after its child has focus and
        # has consumed its own navigation bindings.
        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        assert app.game.paused is False


@pytest.mark.asyncio
async def test_diagnostics_body_fits_without_scrolling_in_roomy_terminal():
    """The capped modal presents the complete standard snapshot when space allows."""
    app = SnakeApp()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, DiagnosticsModal)
        container = modal.query_one("#diagnostics-container", Vertical)
        prompt = modal.query_one("#diagnostics-prompt", Static)
        scroll = modal.query_one("#diagnostics-scroll", VerticalScroll)
        params = modal.query_one("#diagnostics-params", Static)

        assert container.region.width <= 72
        assert container.region.height <= 46
        _assert_fully_in_view(prompt, 120, 50)
        _assert_fully_in_view(scroll, 120, 50)
        assert scroll.max_scroll_y == 0
        assert params.region.bottom <= scroll.content_region.bottom


@pytest.mark.asyncio
async def test_diagnostics_shows_live_config_and_state():
    """The overlay reports key config/state pairs reflecting the live game."""
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        text = app.screen._params_text()
        # A few representative pairs, including the ones that explain board sizing.
        assert "grid cap" in text
        assert "cell scale (k)" in text
        assert f"{app.game.width} x {app.game.height}" in text  # logical grid value
        assert "demo strategy" in text
        assert "walls : True" in text


@pytest.mark.asyncio
async def test_diagnostics_copy_to_clipboard(monkeypatch):
    """Pressing C copies the diagnostics text to the clipboard.

    Force the OSC 52 path (no local clipboard tool) so the result is observable
    via `app.clipboard` regardless of what's installed in the test environment.
    """
    monkeypatch.setattr("snek.clipboard._system_clipboard_command", lambda: None)
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        expected = app.screen._params_text()

        await pilot.press("c")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.clipboard == expected


async def _open_diagnostics_capturing_notify(app, pilot):
    """Open the diagnostics overlay and capture its `notify` calls."""
    await pilot.press("space")
    await pilot.pause()
    await pilot.press("question_mark")
    await pilot.pause()
    calls: list[tuple[tuple, dict]] = []
    app.screen.notify = lambda *a, **k: calls.append((a, k))
    return calls


@pytest.mark.asyncio
async def test_diagnostics_copy_warns_on_osc52_fallback(monkeypatch):
    """When no local clipboard tool exists, the copy toast warns about it."""
    monkeypatch.setattr("snek.clipboard._system_clipboard_command", lambda: None)
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        calls = await _open_diagnostics_capturing_notify(app, pilot)
        await pilot.press("c")
        await app.workers.wait_for_complete()
        await pilot.pause()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert kwargs.get("severity") == "warning"
    message = args[0]
    assert "OSC 52" in message
    assert "clipboard tool" in message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "detail",
    [
        "System clipboard command timed out",
        "System clipboard command exited with status 3",
    ],
)
async def test_diagnostics_copy_reports_system_failure(
    monkeypatch: pytest.MonkeyPatch, detail: str
) -> None:
    """Timeout and non-zero fallback notifications retain their concise reason."""

    async def copy_with_fallback(  # ruff: ignore[unused-async] - mocks an async API
        _app: object, _text: str
    ) -> clipboard.CopyResult:
        return clipboard.CopyResult(clipboard.METHOD_OSC52, detail)

    monkeypatch.setattr(clipboard, "copy_text", copy_with_fallback)
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        calls = await _open_diagnostics_capturing_notify(app, pilot)
        await pilot.press("c")
        await app.workers.wait_for_complete()
        await pilot.pause()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert kwargs.get("severity") == "warning"
    assert detail in args[0]
    assert "OSC 52" in args[0]


@pytest.mark.asyncio
async def test_diagnostics_copy_confirms_system_clipboard(monkeypatch):
    """When a local tool is used, the toast confirms it without warning."""

    async def copy_to_system(  # ruff: ignore[unused-async] - mocks an async API
        _app: object, _text: str
    ) -> clipboard.CopyResult:
        return clipboard.CopyResult(clipboard.METHOD_SYSTEM)

    monkeypatch.setattr(clipboard, "copy_text", copy_to_system)
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        calls = await _open_diagnostics_capturing_notify(app, pilot)
        await pilot.press("c")
        await app.workers.wait_for_complete()
        await pilot.pause()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert kwargs.get("severity") != "warning"
    assert "system clipboard" in args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("close_mode", ["screen", "app"])
async def test_slow_clipboard_worker_keeps_ui_responsive_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch, close_mode: str
) -> None:
    """A hung utility does not block timers/input and is reaped when the modal closes."""
    started = asyncio.Event()

    class SlowClipboardProcess:
        def __init__(self) -> None:
            self.returncode: int | None = None
            self.killed = False
            self.waited = False

        async def communicate(self, input: bytes) -> tuple[bytes, bytes]:
            started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        def kill(self) -> None:
            self.killed = True
            self.returncode = -9

        async def wait(self) -> int:
            self.waited = True
            assert self.returncode is not None
            return self.returncode

    process = SlowClipboardProcess()

    async def create_process(  # ruff: ignore[unused-async] - mocks an async API
        *_args: object, **_kwargs: object
    ) -> SlowClipboardProcess:
        return process

    monkeypatch.setattr(clipboard, "_system_clipboard_command", lambda: ["wl-copy"])
    monkeypatch.setattr(clipboard.asyncio, "create_subprocess_exec", create_process)
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, DiagnosticsModal)

        await pilot.press("c")
        await asyncio.wait_for(started.wait(), timeout=0.5)

        loop_responsive = asyncio.Event()
        app.set_timer(0.01, loop_responsive.set)
        await asyncio.wait_for(loop_responsive.wait(), timeout=0.5)

        if close_mode == "screen":
            # SPACE must still be processed while the five-second clipboard
            # timeout is pending. Popping the owner cancels its worker.
            await pilot.press("space")
            await pilot.pause()
            assert isinstance(app.screen, GameScreen)
        else:
            workers = list(app.workers)
            assert len(workers) == 1
            app.exit()
            with pytest.raises(WorkerCancelled):
                await workers[0].wait()
        if close_mode == "screen":
            await app.workers.wait_for_complete()
        await pilot.pause()

        assert process.killed and process.waited
        assert not list(app.workers)


class TestWorldProgression:
    """Test world progression."""

    def test_check_world_transition(self):
        """Test world transition when enough symbols consumed in current world."""
        from snek.game import Game

        game = Game()
        game.symbols_in_current_world = 10  # Assuming default symbols_per_world is 10
        game.check_world_transition()
        assert game.current_world == 1
        assert game.symbols_in_current_world == 0  # Resets for new world

        # Test multiple world transitions
        game.symbols_in_current_world = 10
        game.check_world_transition()
        assert game.current_world == 2

    def test_get_moves_per_second(self):
        """Test moves per second calculation."""
        from snek.game import Game

        game = Game()
        game.current_interval = 0.1
        assert game.get_moves_per_second() == pytest.approx(10.0)

        game.current_interval = 0.5
        assert game.get_moves_per_second() == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_settings_open_from_the_splash_and_fit_80_by_24() -> None:
    app = SnakeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("s")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SettingsModal)
        for widget in modal.query(Static):
            _assert_fully_in_view(widget, 80, 24)
        for part in ("#settings-title", "#settings-rows", "#settings-help"):
            _assert_horizontally_centred(modal.query_one(part), 80)
        first = modal.query_one("#setting-0", Static)
        assert first.has_class("-selected")
        assert "Mode" in str(first.render())
        assert "Classic" in str(first.render())

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, SplashScreen)


@pytest.mark.asyncio
async def test_settings_apply_to_the_next_game() -> None:
    """Changing walls and speed on the settings screen changes the next game."""
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("s")
        await pilot.pause()
        await pilot.press("down", "right")  # walls off
        await pilot.press("down", "left")  # speed 10 -> 8 moves/sec
        await pilot.pause()
        assert app.config.walls is False
        assert app.config.initial_speed_interval == pytest.approx(1 / 8)
        help_text = str(app.screen.query_one("#settings-help", Static).render())
        assert "Moves per second" in help_text

        await pilot.press("enter")
        await pilot.press("space")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        game_screen._disarm()
        assert app.game.config is app.config
        assert app.game.current_interval == pytest.approx(1 / 8)
        view = game_screen.query_one(SnakeView)
        assert "┏" not in _board_text(view)  # no heavy wall frame


@pytest.mark.asyncio
async def test_layout_settings_re_establish_the_grid_for_the_next_game() -> None:
    """The grid is fixed during a game, but a new game after changing the grid
    cap uses the new cap."""
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        assert (app.game.width, app.game.height) == (36, 20)
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        game_screen._disarm()
        app.game.game_over = True
        app.pop_screen()
        await pilot.pause()
        assert isinstance(app.screen, SplashScreen)

        await pilot.press("s")
        await pilot.pause()
        await pilot.press("down", "down", "down", "down", "left")  # 36x20 -> 24x14
        await pilot.press("escape", "space")
        await pilot.pause()
        assert (app.game.width, app.game.height) == (24, 14)
        assert not app.game.game_over


@pytest.mark.asyncio
async def test_splash_prompt_offers_the_demo_and_settings() -> None:
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        prompt = str(app.screen.query_one("#splash-start-prompt", Static).render())
        assert prompt == (
            "Press SPACE to start, D to run the demo, ←/→ to change mode, "
            "or S for detailed settings."
        )


@pytest.mark.asyncio
async def test_splash_mode_sits_below_the_prompts_and_above_the_version() -> None:
    app = SnakeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        screen = app.screen
        order = [
            screen.query_one(f"#{name}").region.y
            for name in (
                "splash-start-prompt",
                "splash-controls-prompt",
                "splash-mode",
                "splash-mode-help",
                "splash-version",
            )
        ]
        assert order == sorted(order)


def _splash_mode(app: SnakeApp) -> tuple[str, str]:
    """The splash's mode line and its description, as plain text."""
    screen = app.screen
    assert isinstance(screen, SplashScreen)
    return (
        str(screen.query_one("#splash-mode", Static).render()),
        str(screen.query_one("#splash-mode-help", Static).render()),
    )


@pytest.mark.asyncio
async def test_splash_cycles_the_mode_and_applies_it() -> None:
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        line, description = _splash_mode(app)
        assert line == "◂ Classic ▸"
        assert "fixed 36x20 walled board" in description

        await pilot.press("right")
        await pilot.pause()
        assert _splash_mode(app)[0] == "◂ Arcade ▸"
        assert app.config.food_sprites is True
        assert (app.config.max_grid_width, app.config.max_grid_height) == (20, 12)

        await pilot.press("left", "left")
        await pilot.pause()
        assert _splash_mode(app)[0] == "◂ Pixel Arena ▸"
        assert app.config.sizing_mode == "fill"
        assert app.config.walls is False

        # The next game plays the chosen mode.
        await pilot.press("space")
        await pilot.pause()
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        game_screen._disarm()
        assert app.game.config is app.config


@pytest.mark.asyncio
async def test_settings_tweaks_show_as_custom_on_the_splash_and_back() -> None:
    """The mode is derived from the settings: tweak away from a mode and the
    splash shows Custom; tweak back onto its values and it shows the mode."""
    app = SnakeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("s")
        await pilot.pause()
        await pilot.press("down", "right")  # walls off
        await pilot.pause()
        first_row = str(app.screen.query_one("#setting-0", Static).render())
        assert "Custom" in first_row
        await pilot.press("up")  # the Mode row describes the current mode
        await pilot.pause()
        help_text = str(app.screen.query_one("#settings-help", Static).render())
        assert "Your own mix" in help_text
        await pilot.press("escape")
        await pilot.pause()
        line, description = _splash_mode(app)
        assert line == "◂ Custom ▸"
        assert "Your own mix" in description

        await pilot.press("s")
        await pilot.pause()
        await pilot.press("down", "right")  # walls back on
        await pilot.press("escape")
        await pilot.pause()
        assert _splash_mode(app)[0] == "◂ Classic ▸"

        # From Custom, the splash enters the modes at either end.
        app.apply_settings(
            replace(app.settings, config=replace(app.config, walls=False))
        )
        await pilot.press("right")
        await pilot.pause()
        assert _splash_mode(app)[0] == "◂ Classic ▸"


@pytest.mark.asyncio
async def test_too_small_message_fits_the_supported_minimum() -> None:
    """Arcade at 80x24 is held, and its message fits the narrow view whole."""
    app = SnakeApp(config=apply_mode(default_config, "Arcade"))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        snake_view = app.screen.query_one(SnakeView)
        assert snake_view.too_small
        text = _board_text(snake_view)
        assert "Needs 112 x 26; this is 80 x 24." in text
        assert "Enlarge the window or turn sprites off." in text
        assert "ESC main menu" in text


@pytest.mark.asyncio
async def test_settings_help_fits_the_longest_help_on_one_line() -> None:
    app = SnakeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("s")
        await pilot.pause()
        help_line = app.screen.query_one("#settings-help", Static)
        assert help_line.region.width > widest_help()
        _assert_fully_in_view(help_line, 80, 24)
        for _ in ROWS:
            text = str(help_line.render())
            assert (
                help_line.render_lines(help_line.region.reset_offset)[0].text.strip()
                == text
            )
            await pilot.press("down")
            await pilot.pause()


@pytest.mark.asyncio
async def test_game_over_prompt_fits_one_line_under_a_centred_title():
    """The restart prompt is wider than the title yet stays on one line."""
    app = SnakeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        app.screen._disarm()
        app.push_screen(GameOverModal())
        await pilot.pause()
        modal = app.screen
        _assert_horizontally_centred(modal.query_one("#death-title"), 80)
        for prompt in modal.query(".death-prompt"):
            assert prompt.region.height == 1
