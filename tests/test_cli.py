"""Tests for the `snek` CLI, including the `--demo-strategy` selector."""

import pytest

from snek.app import SnakeApp
from snek.cli import _build_parser
from snek.demo import DEFAULT_STRATEGY, STRATEGIES
from snek.screens import GameScreen


def test_parser_default_is_default_strategy():
    """With no flag, `--demo-strategy` defaults to the active default strategy."""
    assert _build_parser().parse_args([]).demo_strategy == DEFAULT_STRATEGY


@pytest.mark.parametrize("name", list(STRATEGIES))
def test_parser_accepts_each_registered_strategy(name):
    """Every registry key is a valid `--demo-strategy` choice."""
    assert _build_parser().parse_args(["--demo-strategy", name]).demo_strategy == name


def test_parser_rejects_unknown_strategy():
    """An unknown strategy is rejected by argparse (exits non-zero)."""
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--demo-strategy", "does-not-exist"])


def test_app_default_demo_strategy():
    """A plain app uses the default strategy."""
    assert SnakeApp().demo_strategy == DEFAULT_STRATEGY


def test_app_stores_demo_strategy():
    """The app records the selected strategy for the game screen to use."""
    assert SnakeApp(demo_strategy="hamiltonian").demo_strategy == "hamiltonian"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(STRATEGIES))
async def test_demo_mode_uses_selected_strategy(name):
    """Pressing D builds the strategy named by `--demo-strategy`; restart keeps it."""
    app = SnakeApp(demo_strategy=name)
    async with app.run_test() as pilot:
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        assert isinstance(app.screen.demo_ai, STRATEGIES[name])

        app.screen.restart_game()  # restart preserves the selected strategy
        assert isinstance(app.screen.demo_ai, STRATEGIES[name])
