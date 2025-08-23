"""Tests for demo mode functionality."""

import pytest

from snek.app import SnakeApp
from snek.screens import GameScreen


@pytest.mark.asyncio
async def test_demo_mode_startup():
    """Test that demo mode starts without errors."""
    app = SnakeApp()
    async with app.run_test() as pilot:
        # Start demo mode (press 'd' key)
        await pilot.press("d")
        await pilot.pause()
        
        # Should now be on game screen
        assert isinstance(app.screen, GameScreen)
        
        # Demo AI should be enabled
        game_screen = app.screen
        assert game_screen.demo_ai is not None
        
        # Game should be running
        assert app.game.is_running
        
        # Let the game tick a few times to test AI functionality
        for _ in range(3):
            game_screen.tick()
            await pilot.pause(0.1)


@pytest.mark.asyncio 
async def test_demo_mode_restart():
    """Test restarting the game in demo mode."""
    app = SnakeApp()
    async with app.run_test() as pilot:
        # Start demo mode
        await pilot.press("d")
        await pilot.pause()
        
        game_screen = app.screen
        assert isinstance(game_screen, GameScreen)
        assert game_screen.demo_ai is not None
        
        # Test restart functionality
        game_screen.restart_game()
        
        # Demo AI should still be enabled after restart
        assert game_screen.demo_ai is not None
        assert app.game.is_running