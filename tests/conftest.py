"""Pytest configuration and fixtures."""

from collections.abc import Generator

import pytest

from snek.config import GameConfig
from snek.screens import GameScreen
from tests.snapshot_safety import sanitized_snapshot_environment


@pytest.fixture(autouse=True)
def stopped_game_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop every game's clock, so a started game never steps on its own.

    The loop credits wall time, so on a loaded machine a stall of a second or two let a
    live game run the snake into a wall mid-test. Tests advance the game with
    `GameScreen.tick()`, or give a screen its own clock (`game_screen._now`) and wake it.
    """
    monkeypatch.setattr(GameScreen, "_now", staticmethod(lambda: 0.0))


@pytest.fixture
def deterministic_snapshot_render_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Give visual snapshots a canonical color-capable terminal environment.

    Textual reads these variables when each ``App`` is constructed. Keeping the
    fixture opt-in lets ordinary tests continue to exercise ambient and explicit
    monochrome behavior while checked-in SVG baselines remain host-independent.
    """
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("COLORTERM", "truecolor")


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_sessionfinish(
    session: pytest.Session, exitstatus: int
) -> Generator[None, None, None]:
    """Prevent snapshot failure reports from serializing the host environment.

    pytest-textual-snapshot renders ``os.environ`` during its own session-finish
    hook. Wrapping it with a non-reporting environment proxy keeps credentials
    and attacker-controlled markup out of the HTML report while preserving the
    plugin's operational lookups. The original environment is restored after
    all session-finish hooks have completed.
    """
    with sanitized_snapshot_environment():
        yield


@pytest.fixture
def default_config():
    """Provide default game configuration."""
    return GameConfig()


@pytest.fixture
def mock_rng():
    """Provide a seeded random number generator for deterministic tests."""
    import random

    return random.Random(42)
