"""Pytest configuration and fixtures."""

import pytest
from snek.config import GameConfig


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
    config.speed_increase_factor = 1.1
    return config


@pytest.fixture
def mock_rng():
    """Provide a seeded random number generator for deterministic tests."""
    import random

    return random.Random(42)
