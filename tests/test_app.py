"""Integration tests for the Snek app."""

import asyncio

import pytest
from textual.containers import Vertical, VerticalScroll
from textual.worker import WorkerCancelled
from textual.widgets import Label, Static

from snek import clipboard
from snek.app import SnakeApp
from snek.config import GameConfig
from snek.figlet import FigletText
from snek.game_rules import Direction
from snek.screens import (
    DiagnosticsModal,
    GameScreen,
    GameOverModal,
    SplashScreen,
    SnakeView,
    SidePanel,
    StatDisplay,
)


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
    for first, second in zip(game.snake, game.snake[1:]):
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

        assert not large_title.display
        assert compact_title.display
        assert large_title._timer is None
        assert compact_title._timer is None
        for widget in (compact_title, start_prompt, controls_prompt, version):
            _assert_fully_in_view(widget, 80, 24)

        assert compact_title.region.height == len(compact_title._lines) == 5
        assert start_prompt.region.height == controls_prompt.region.height == 1
        assert "SPACE to start" in str(start_prompt.render())
        assert "Q to quit" in str(controls_prompt.render())


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
        _assert_fully_in_view(screen.query_one("#splash-start-prompt"), 120, 40)
        _assert_fully_in_view(screen.query_one("#splash-controls-prompt"), 120, 40)
        _assert_fully_in_view(screen.query_one("#splash-version"), 120, 40)
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
        assert title._animate is expected
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
        game_screen.timer.stop()

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
        game_screen.timer.stop()
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
        game_screen.timer.stop()
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

        # Force world change by consuming enough symbols to get to a world with a different theme
        # World 0 uses 'snek-classic', world 1 uses 'snek-ocean'
        game.symbols_consumed = config.symbols_per_world
        game.symbols_in_current_world = config.symbols_per_world
        game.check_world_transition()
        await pilot.pause()

        # World should have changed
        assert game.current_world == old_world + 1

        # Manually trigger theme change since we bypassed the normal game step
        if game.current_world != old_world:
            app.theme = game.world_path.get_world(game.current_world).theme_name

        await pilot.pause()

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
        game_screen.timer.stop()

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
        game_screen.timer.stop()
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
    app = SnakeApp()
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
    app = SnakeApp(config=GameConfig(sizing_mode="fill", cell_scale=1))
    async with app.run_test(size=(172, 48)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        snake_view = app.screen.query_one(SnakeView)
        # At scale 1 the grid fills the view (~width/2 cells), well past the cap.
        assert app.game.width > app.config.max_grid_width
        assert app.game.width == snake_view.size.width // 2
        assert snake_view._scale == 1


def _board_text(snake_view) -> str:
    """Flatten a SnakeView's rendered Segments to plain text."""
    return "".join(seg.text for seg in snake_view.render().segments)


@pytest.mark.asyncio
async def test_food_uses_glyph_at_scale_one():
    """On a small terminal (scale 1) food is the themed glyph, not a sprite."""
    app = SnakeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        app.screen.timer.stop()
        game = app.game
        game.reset()
        hx, hy = game.snake[0]
        game.set_food_position((hx + 3, hy))
        text = _board_text(app.screen.query_one(SnakeView))
        assert game.food_symbol in text  # glyph drawn
        assert "▄" not in text  # no sprite pixels


@pytest.mark.asyncio
async def test_food_uses_sprite_at_large_scale():
    """On a large terminal (scale >= 2) food is drawn as a pixel sprite."""
    app = SnakeApp()
    async with app.run_test(size=(280, 70)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        app.screen.timer.stop()
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
        app.screen.timer.stop()
        game = app.game
        game.reset()
        hx, hy = game.snake[0]
        game.set_food_position((hx + 3, hy))
        text = _board_text(app.screen.query_one(SnakeView))
        assert game.food_symbol in text
        assert "▄" not in text


@pytest.mark.asyncio
async def test_scale_only_resize_does_not_rescale_snake():
    """Growing the terminal changes scale while leaving the fixed grid intact."""
    app = SnakeApp()
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        app.screen.timer.stop()
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

    async def copy_with_fallback(_app: object, _text: str) -> clipboard.CopyResult:
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

    async def copy_to_system(_app: object, _text: str) -> clipboard.CopyResult:
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

        async def communicate(self, input: bytes) -> tuple[bytes, bytes]:  # noqa: A002
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

    async def create_process(*_args: object, **_kwargs: object) -> SlowClipboardProcess:
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
        assert game.get_moves_per_second() == 10.0

        game.current_interval = 0.5
        assert game.get_moves_per_second() == 2.0
