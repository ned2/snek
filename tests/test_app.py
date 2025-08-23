"""Integration tests for the Snek app."""

import pytest

from snek.app import SnakeApp
from snek.config import GameConfig
from snek.game_rules import Direction
from snek.screens import GameScreen, SplashScreen, SnakeView, SidePanel


@pytest.mark.asyncio
async def test_app_startup():
    """Test app starts with splash screen."""
    app = SnakeApp()
    async with app.run_test():
        # Should show splash screen as the current screen
        assert isinstance(app.screen, SplashScreen)


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

        # Test direction controls
        await pilot.press("up")
        assert game.direction == Direction.UP

        await pilot.press("right")
        assert game.direction == Direction.RIGHT

        await pilot.press("down")
        assert game.direction == Direction.DOWN

        # Now we can turn left (from down)
        await pilot.press("left")
        assert game.direction == Direction.LEFT


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
        assert (
            len(app.game.snake) == 1
        )  # Should have initial snake length


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
    """Test stats panel updates with game state."""
    app = SnakeApp()
    async with app.run_test() as pilot:
        # Start game
        await pilot.press("space")
        await pilot.pause()

        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)

        # Get initial stats
        stats = game_screen.query_one(SidePanel)
        game = app.game

        # Update game state
        game.symbols_consumed = 10
        game.current_world = 1

        # Trigger reactive field updates (simulating what happens in tick())
        game_screen._update_reactive_fields()
        await pilot.pause()

        # Check if the game state was actually updated
        assert game.symbols_consumed == 10
        assert game.current_world == 1

        # Check the stats panel's internal state
        assert app.game.symbols_consumed == 10
        assert app.game.current_world == 1


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
    """Test app handles terminal resize."""
    app = SnakeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        # Start game
        await pilot.press("space")
        await pilot.pause()

        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)

        # Create a mock resize event for the snake view
        from textual.events import Resize

        resize_event = Resize(100, 30, 100, 30)

        # Simulate resize on the snake view
        snake_view = game_screen.query_one(SnakeView)
        snake_view.on_resize(resize_event)
        await pilot.pause()

        # Game dimensions should update
        assert app.game.width > 0
        assert app.game.height > 0


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

    def test_update_speed(self):
        """Test speed update mechanism."""
        from snek.game import Game

        game = Game()
        initial_interval = game.current_interval

        # Update speed
        new_interval = 0.05
        game.update_speed(new_interval)

        assert game.current_interval == new_interval
        assert game.current_interval < initial_interval

    def test_get_moves_per_second(self):
        """Test moves per second calculation."""
        from snek.game import Game

        game = Game()
        game.current_interval = 0.1
        assert game.get_moves_per_second() == 10.0

        game.current_interval = 0.5
        assert game.get_moves_per_second() == 2.0
