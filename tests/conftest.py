"""Pytest configuration and fixtures."""

from collections.abc import Generator

import pytest
from snek.config import GameConfig

from tests.snapshot_safety import sanitized_snapshot_environment


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
def test_config():
    """Provide test-specific game configuration."""
    config = GameConfig()
    config.default_grid_width = 20
    config.default_grid_height = 20
    config.initial_speed_interval = 0.1
    config.speed_increase_factor = 0.9
    return config


@pytest.fixture
def mock_rng():
    """Provide a seeded random number generator for deterministic tests."""
    import random

    return random.Random(42)
