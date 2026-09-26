"""Tests for the game modes (`snek.modes`)."""

from dataclasses import fields, replace

import pytest

from snek.config import GameConfig, default_config
from snek.modes import (
    CUSTOM,
    DEFAULT_MODE,
    MODES,
    Mode,
    apply_mode,
    describe,
    mode_of,
)


def test_defaults_are_the_default_mode() -> None:
    assert DEFAULT_MODE.name == "Classic"
    assert mode_of(default_config) == "Classic"


@pytest.mark.parametrize("mode", MODES, ids=lambda mode: mode.key)
def test_every_mode_is_valid_and_recognised(mode: Mode) -> None:
    """Applying a mode from any other mode lands on exactly that mode."""
    for start in MODES:
        config = apply_mode(apply_mode(default_config, start.name), mode.name)
        assert mode_of(config) == mode.name


@pytest.mark.parametrize("mode", MODES, ids=lambda mode: mode.key)
def test_modes_own_only_config_fields(mode: Mode) -> None:
    names = {field.name for field in fields(GameConfig)}
    assert set(mode.values) <= names


def test_modes_are_distinct() -> None:
    assert len({tuple(sorted(mode.values.items())) for mode in MODES}) == len(MODES)


def test_the_agreed_modes() -> None:
    """Walled fixed boards; wrapping boards that fill the terminal."""
    by_name = {mode.name: mode.values for mode in MODES}
    assert list(by_name) == ["Classic", "Arcade", "Arena", "Pixel Arena"]
    for name in ("Classic", "Arcade"):
        assert by_name[name]["walls"] is True
        assert by_name[name]["sizing_mode"] == "cap"
    for name in ("Arena", "Pixel Arena"):
        assert by_name[name]["walls"] is False
        assert by_name[name]["sizing_mode"] == "fill"
    for name in ("Arcade", "Pixel Arena"):
        assert by_name[name]["food_sprites"] is True


def test_changing_an_owned_value_is_custom() -> None:
    assert mode_of(replace(default_config, walls=False)) == CUSTOM
    assert mode_of(replace(default_config, max_grid_width=48)) == CUSTOM


def test_unowned_values_do_not_change_the_mode() -> None:
    config = replace(default_config, smooth_motion=False, initial_speed_interval=0.5)
    assert mode_of(config) == "Classic"


def test_fill_modes_ignore_the_grid_cap() -> None:
    """Fill sizing never reads the cap, so it cannot make Arena Custom."""
    arena = apply_mode(default_config, "Arena")
    assert mode_of(replace(arena, max_grid_width=60, max_grid_height=34)) == "Arena"


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
