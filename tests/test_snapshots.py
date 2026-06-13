"""Visual snapshot test guarding the game-screen render.

A baseline SVG of the game screen catches silent rendering regressions — notably
the Textual 6.0.0 change that stopped applying background styles to widget
*content* (see `issues/0002-design-audit/research.md` §4). Regenerate the baseline
with `uv run pytest --snapshot-update` after an intentional visual change.
"""

from snek.app import SnakeApp
from snek.screens import SnakeView


def test_game_screen_snapshot(snap_compare):
    """The game screen (board + stats panel) matches its baseline render."""
    app = SnakeApp()

    async def run_before(pilot) -> None:
        # Splash -> game, then pin the board to a deterministic state: stop the
        # loop and reset the snake to center, then fix the food cell + symbol so
        # the capture never depends on timer ticks or RNG.
        await pilot.press("space")
        await pilot.pause()
        screen = pilot.app.get_screen("game")
        if screen.timer is not None:
            screen.timer.stop()
        game = pilot.app.game
        game.reset()
        head_x, head_y = game.snake[0]
        game.set_food_position((head_x + 3, head_y), symbol="🍎")
        screen._sync_reactives()
        screen.query_one(SnakeView).refresh()
        await pilot.pause()

    assert snap_compare(app, terminal_size=(80, 24), run_before=run_before)
