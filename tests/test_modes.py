"""Tests for the game modes (`snek.modes`)."""

from dataclasses import replace

import pytest

from snek.config import default_config
from snek.demo import DEFAULT_STRATEGY, STRATEGIES
from snek.modes import (
    CUSTOM,
    DEFAULT_MODE,
    MODE_FIELDS,
    MODES,
    Mode,
    Settings,
    apply_mode,
    default_settings,
    describe,
    mode_of,
)
from snek.settings import MODE_ROW, ROWS


def test_defaults_are_the_default_mode() -> None:
    assert DEFAULT_MODE.name == "Classic"
    assert mode_of(default_settings()) == "Classic"
    assert default_settings().demo_strategy == DEFAULT_STRATEGY


@pytest.mark.parametrize("mode", MODES, ids=lambda mode: mode.key)
def test_every_mode_is_valid_and_recognised(mode: Mode) -> None:
    """Applying a mode from any other mode lands on exactly that mode."""
    for start in MODES:
        settings = apply_mode(apply_mode(default_settings(), start.name), mode.name)
        assert settings.error() is None
        assert mode_of(settings) == mode.name


@pytest.mark.parametrize("mode", MODES, ids=lambda mode: mode.key)
def test_every_mode_gives_every_setting(mode: Mode) -> None:
    """Modes are exhaustive: each gives exactly the settings-screen fields."""
    assert set(mode.values) == MODE_FIELDS
    assert mode.demo_strategy in STRATEGIES


def test_mode_fields_are_the_settings_screen_fields() -> None:
    """Every settings row but Mode edits the demo strategy or a mode field, and
    together they edit every mode field."""
    edited: set[str] = set()
    start = default_settings()
    for row in ROWS:
        if row is MODE_ROW:
            continue
        for choice in row.choices:
            edited |= set(row.put(start, choice).values)
    assert edited == MODE_FIELDS


def test_modes_are_distinct() -> None:
    assert len({tuple(sorted(mode.values.items())) for mode in MODES}) == len(MODES)


def test_the_agreed_modes() -> None:
    """Classic is Nokia Snake's walled 20x11 board; the rest fill the terminal,
    and only the Arenas wrap."""
    by_name = {mode.name: mode.values for mode in MODES}
    assert list(by_name) == ["Classic", "Arcade", "Arena", "Pixel Arena"]
    classic = by_name["Classic"]
    assert classic["sizing_mode"] == "cap"
    assert (classic["max_grid_width"], classic["max_grid_height"]) == (20, 11)
    assert classic["start_length"] == 8
    assert classic["food_type"] == "diamond"
    for name in ("Arcade", "Arena", "Pixel Arena"):
        assert by_name[name]["sizing_mode"] == "fill"
        assert by_name[name]["start_length"] == 3
    for name in ("Classic", "Arcade"):
        assert by_name[name]["walls"] is True
    for name in ("Arena", "Pixel Arena"):
        assert by_name[name]["walls"] is False
    assert by_name["Arena"]["food_type"] == "glyphs"
    for name in ("Arcade", "Pixel Arena"):
        assert by_name[name]["food_type"] == "sprites"


def test_the_agreed_worlds() -> None:
    """Classic stays in world 5 (10 moves a second) on the LCD screen; the other
    modes progress from world 1 in each world's colours, with foods per world
    suited to the board."""
    worlds = {
        mode.name: (
            mode.values["start_world"],
            mode.values["world_change"],
            mode.values["foods_per_world"],
            mode.values["palette"],
        )
        for mode in MODES
    }
    assert worlds == {
        "Classic": (5, "fixed", 50, "lcd"),
        "Arcade": (1, "progress", 25, "worlds"),
        "Arena": (1, "progress", 200, "worlds"),
        "Pixel Arena": (1, "progress", 100, "worlds"),
    }
    assert "LCD" in describe("Classic")


def test_changing_any_setting_is_custom() -> None:
    settings = default_settings()
    for change in (
        {"walls": False},
        {"max_grid_width": 48},
        {"smooth_motion": False},
        {"start_length": 3},
        {"start_world": 1},
        {"world_change": "progress"},
        {"foods_per_world": 10},
        {"palette": "worlds"},
    ):
        assert mode_of(settings.with_values(**change)) == CUSTOM
    assert mode_of(replace(settings, demo_strategy="greedy")) == CUSTOM


def test_settings_outside_modes_do_not_change_the_mode() -> None:
    settings = default_settings().with_values(max_buffered_turns=5)
    assert mode_of(settings) == "Classic"


def test_invalid_settings_are_custom_and_say_why() -> None:
    settings = default_settings().with_values(food_type="sprites", cell_scale=1)
    assert mode_of(settings) == CUSTOM
    assert settings.error() == "food sprites need a cell scale of at least 2, got 1"
    with pytest.raises(ValueError):
        settings.to_config()


def test_settings_read_values_over_the_base() -> None:
    settings = Settings(base=default_config, demo_strategy="greedy")
    assert settings.get("walls") is default_config.walls
    changed = settings.with_values(walls=False)
    assert changed.get("walls") is False
    assert changed.to_config() == replace(default_config, walls=False)
    assert settings.get("walls") is default_config.walls  # unchanged


def test_keys_and_descriptions() -> None:
    assert [mode.key for mode in MODES] == [
        "classic",
        "arcade",
        "arena",
        "pixel-arena",
    ]
    for mode in MODES:
        assert describe(mode.name) == mode.description
    assert describe(CUSTOM)
