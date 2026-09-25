"""Unit tests for the settings rows (`snek.settings`)."""

from dataclasses import replace

import pytest

from snek.config import GameConfig, default_config
from snek.demo import STRATEGIES
from snek.settings import ROWS, SPEEDS, SettingRow, Settings


def _row(label: str) -> SettingRow:
    return next(row for row in ROWS if row.label == label)


def _defaults() -> Settings:
    return Settings(config=default_config, demo_strategy="floodfill")


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row.label)
def test_every_choice_makes_a_valid_config(row: SettingRow) -> None:
    """Each choice applies through `GameConfig` validation and reads back."""
    for choice in row.choices:
        settings = row.put(_defaults(), choice)
        assert isinstance(settings.config, GameConfig)
        assert row.get(settings) == choice
        assert row.value_text(settings)


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row.label)
def test_defaults_are_choices(row: SettingRow) -> None:
    """Without CLI overrides every row starts on one of its own choices."""
    assert row.get(_defaults()) in row.choices


def test_named_settings_wrap_round() -> None:
    walls = _row("Walls")
    on = walls.step(_defaults(), 1)
    assert on.config.walls is True
    assert walls.step(on, 1).config.walls is False
    assert walls.step(_defaults(), -1).config.walls is True


def test_ordered_settings_stop_at_the_ends() -> None:
    speed = _row("Starting speed")
    fastest = speed.put(_defaults(), SPEEDS[-1])
    assert speed.step(fastest, 1) == fastest
    slowest = speed.put(_defaults(), SPEEDS[0])
    assert speed.step(slowest, -1) == slowest


def test_speed_is_moves_per_second() -> None:
    speed = _row("Starting speed")
    assert speed.get(_defaults()) == 10
    faster = speed.step(_defaults(), 1)
    assert faster.config.initial_speed_interval == pytest.approx(1 / 12)
    assert speed.value_text(faster) == "12 /sec"


@pytest.mark.parametrize(
    ("moves_per_second", "delta", "expected"),
    [(7.3, 1, 8), (7.3, -1, 6), (100, 1, 100), (100, -1, 50), (1, -1, 1), (1, 1, 2)],
)
def test_off_list_values_step_to_the_nearest_choice(
    moves_per_second: float, delta: int, expected: float
) -> None:
    """A `--speed` between presets steps to the next one; past the ends it stays."""
    speed = _row("Starting speed")
    config = replace(default_config, initial_speed_interval=1 / moves_per_second)
    settings = Settings(config=config, demo_strategy="floodfill")
    assert speed.get(speed.step(settings, delta)) == pytest.approx(expected)


def test_grid_cap_sets_both_dimensions() -> None:
    grid = _row("Grid cap")
    smaller = grid.step(_defaults(), -1)
    assert (smaller.config.max_grid_width, smaller.config.max_grid_height) == (24, 14)
    assert grid.value_text(smaller) == "24 x 14"


def test_demo_strategy_cycles_through_every_strategy() -> None:
    demo = _row("Demo strategy")
    settings = _defaults()
    seen = []
    for _ in STRATEGIES:
        settings = demo.step(settings, 1)
        seen.append(settings.demo_strategy)
    assert sorted(seen) == sorted(STRATEGIES)
    assert settings.config == default_config
