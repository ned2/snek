"""Unit tests for the settings rows (`snek.settings`)."""

from dataclasses import replace

import pytest

from snek.config import GameConfig, default_config
from snek.demo import STRATEGIES
from snek.modes import CUSTOM, MODES, describe
from snek.settings import (
    MODE_ROW,
    ROWS,
    SPEEDS,
    SettingRow,
    Settings,
    widest_help,
)


def _row(label: str) -> SettingRow:
    return next(row for row in ROWS if row.label == label)


def _defaults() -> Settings:
    return Settings(config=default_config, demo_strategy="floodfill")


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row.label)
def test_every_choice_makes_a_valid_config(row: SettingRow) -> None:
    """Each choice applies through `GameConfig` validation and reads back.

    From scale two, where both food styles are valid; sprites at scale one are
    refused (see below).
    """
    base = replace(_defaults(), config=replace(default_config, cell_scale=2))
    for choice in row.choices:
        settings = row.put(base, choice)
        assert isinstance(settings.config, GameConfig)
        assert row.get(settings) == choice
        assert row.value_text(settings)


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row.label)
def test_defaults_are_choices(row: SettingRow) -> None:
    """Without CLI overrides every row starts on one of its own choices."""
    assert row.get(_defaults()) in row.choices


def test_named_settings_wrap_round() -> None:
    walls = _row("Walls")  # (off, on), and on by default
    off = walls.step(_defaults(), 1)
    assert off.config.walls is False
    assert walls.step(off, 1).config.walls is True
    assert walls.step(_defaults(), -1).config.walls is False


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


def test_a_step_to_sprites_at_scale_one_is_refused() -> None:
    """Neither row adjusts the other: the invalid step raises instead."""
    at_scale_one = _row("Cell scale").put(_defaults(), 1)
    with pytest.raises(ValueError, match="food sprites need"):
        _row("Food sprites").step(at_scale_one, 1)
    at_scale_two = _row("Cell scale").put(_defaults(), 2)
    with_sprites = _row("Food sprites").put(at_scale_two, True)
    with pytest.raises(ValueError, match="food sprites need"):
        _row("Cell scale").step(with_sprites, -1)


def test_mode_is_the_first_row_and_starts_on_classic() -> None:
    assert ROWS[0] is MODE_ROW
    assert MODE_ROW.value_text(_defaults()) == "Classic"


def test_stepping_the_mode_applies_each_mode_in_turn() -> None:
    settings = _defaults()
    seen = []
    for _ in MODES:
        seen.append(MODE_ROW.get(settings))
        settings = MODE_ROW.step(settings, 1)
    assert seen == [mode.name for mode in MODES]
    assert MODE_ROW.get(settings) == "Classic"  # wrapped round


def test_tweaking_a_mode_makes_it_custom_and_back() -> None:
    arcade = MODE_ROW.put(_defaults(), "Arcade")
    tweaked = _row("Walls").step(arcade, 1)
    assert MODE_ROW.get(tweaked) == CUSTOM
    assert MODE_ROW.get(_row("Walls").step(tweaked, 1)) == "Arcade"


@pytest.mark.parametrize(("delta", "expected"), [(1, "Classic"), (-1, "Pixel Arena")])
def test_stepping_from_custom_enters_at_the_ends(delta: int, expected: str) -> None:
    custom = _row("Walls").step(_defaults(), 1)
    assert MODE_ROW.get(custom) == CUSTOM
    assert MODE_ROW.get(MODE_ROW.step(custom, delta)) == expected


def test_mode_leaves_unowned_settings_alone() -> None:
    fast = _row("Starting speed").put(_defaults(), SPEEDS[-1])
    arena = MODE_ROW.put(fast, "Arena")
    assert arena.config.initial_speed_interval == fast.config.initial_speed_interval
    assert MODE_ROW.get(fast) == "Classic"


def test_mode_help_describes_the_current_mode() -> None:
    assert MODE_ROW.help_text(_defaults()) == describe("Classic")
    arena = MODE_ROW.put(_defaults(), "Arena")
    assert MODE_ROW.help_text(arena) == describe("Arena")
    custom = _row("Walls").step(_defaults(), 1)
    assert MODE_ROW.help_text(custom) == describe(CUSTOM)


def test_other_rows_have_fixed_help() -> None:
    walls = _row("Walls")
    assert walls.help_text(_defaults()) == walls.help


def test_widest_help_covers_every_help_line() -> None:
    texts = [row.help for row in ROWS if isinstance(row.help, str)]
    texts += [describe(mode.name) for mode in MODES] + [describe(CUSTOM)]
    assert widest_help() == max(len(text) for text in texts)
