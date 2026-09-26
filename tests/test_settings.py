"""Unit tests for the settings rows (`snek.settings`)."""

from dataclasses import replace

import pytest

from snek.config import FOOD_TYPES, default_config
from snek.demo import STRATEGIES
from snek.modes import CUSTOM, MODES, Settings, default_settings, describe
from snek.settings import (
    FOOD_HELP,
    MODE_ROW,
    ROWS,
    SPEEDS,
    START_LENGTHS,
    SettingRow,
    widest_help,
)


def _row(label: str) -> SettingRow:
    return next(row for row in ROWS if row.label == label)


def _defaults() -> Settings:
    return default_settings()


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row.label)
def test_every_choice_makes_a_valid_config(row: SettingRow) -> None:
    """Each choice validates and reads back.

    From scale two, where every food type is valid; sprites at scale one are
    invalid (see below).
    """
    base = _defaults().with_values(cell_scale=2)
    for choice in row.choices:
        settings = row.put(base, choice)
        assert settings.error() is None, (row.label, choice)
        assert row.get(settings) == choice
        assert row.value_text(settings)


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row.label)
def test_defaults_are_choices(row: SettingRow) -> None:
    """Without CLI overrides every row starts on one of its own choices."""
    assert row.get(_defaults()) in row.choices


def test_named_settings_wrap_round() -> None:
    walls = _row("Walls")  # (off, on), and on by default
    off = walls.step(_defaults(), 1)
    assert off.get("walls") is False
    assert walls.step(off, 1).get("walls") is True
    assert walls.step(_defaults(), -1).get("walls") is False


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
    assert faster.get("initial_speed_interval") == pytest.approx(1 / 12)
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
    settings = Settings(base=config, demo_strategy="floodfill")
    assert speed.get(speed.step(settings, delta)) == pytest.approx(expected)


def test_starting_length_is_one_to_ten_in_order() -> None:
    length = _row("Starting length")
    assert length.choices == START_LENGTHS == tuple(range(1, 11))
    assert length.get(_defaults()) == 8
    assert length.step(_defaults(), 1).get("start_length") == 9
    longest = length.put(_defaults(), 10)
    assert length.step(longest, 1) == longest  # stops, not wraps
    assert (
        length.help_text(_defaults()) == "Segments the snake unrolls to at the start."
    )


def test_starting_length_follows_starting_speed() -> None:
    labels = [row.label for row in ROWS]
    assert labels.index("Starting length") == labels.index("Starting speed") + 1


def test_grid_cap_sets_both_dimensions() -> None:
    grid = _row("Grid cap")
    assert grid.value_text(_defaults()) == "20 x 11"
    larger = grid.step(_defaults(), 1)
    assert (larger.get("max_grid_width"), larger.get("max_grid_height")) == (24, 14)
    assert grid.value_text(larger) == "24 x 14"


def test_demo_strategy_cycles_through_every_strategy() -> None:
    demo = _row("Demo strategy")
    settings = _defaults()
    seen = []
    for _ in STRATEGIES:
        settings = demo.step(settings, 1)
        seen.append(settings.demo_strategy)
    assert sorted(seen) == sorted(STRATEGIES)
    assert settings.to_config() == default_config


def test_food_type_cycles_and_its_help_follows_the_value() -> None:
    food = _row("Food type")
    assert food.choices == FOOD_TYPES
    settings = _defaults().with_values(cell_scale=2)
    for _ in FOOD_TYPES:
        value = food.get(settings)
        assert food.value_text(settings) == value.capitalize()
        assert food.help_text(settings) == FOOD_HELP[value]
        settings = food.step(settings, 1)
    assert food.get(settings) == "diamond"  # wrapped round


def test_rows_step_into_invalid_settings() -> None:
    """Neither row refuses or adjusts the other: the settings become invalid and
    say why, and stepping on makes them valid again."""
    food = _row("Food type")
    sprites = food.put(_defaults(), "sprites")  # Classic's cell scale is one
    assert sprites.error() == "food sprites need a cell scale of at least 2, got 1"
    assert MODE_ROW.get(sprites) == CUSTOM
    assert food.step(sprites, 1).error() is None  # wrapped round to diamond
    assert _row("Cell scale").step(sprites, 1).error() is None


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


def test_a_mode_sets_every_setting() -> None:
    """Modes are exhaustive: speed and the demo strategy reset with the mode."""
    tweaked = _row("Starting speed").put(_defaults(), SPEEDS[-1])
    tweaked = _row("Demo strategy").put(tweaked, "greedy")
    assert MODE_ROW.get(tweaked) == CUSTOM
    arena = MODE_ROW.put(tweaked, "Arena")
    assert arena.get("initial_speed_interval") == pytest.approx(0.1)
    assert arena.demo_strategy == "floodfill"
    assert MODE_ROW.get(arena) == "Arena"


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
    texts += list(FOOD_HELP.values())
    assert widest_help(_defaults()) == max(len(text) for text in texts)
