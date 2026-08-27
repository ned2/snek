"""Tests for the explicit `GameConfig` validation boundary."""

import math
from dataclasses import FrozenInstanceError, replace

import pytest

from snek.config import GameConfig


def test_config_is_an_immutable_value_object() -> None:
    """Overrides create a new validated value and cannot alter the source."""
    config = GameConfig()
    original_scale = config.cell_scale

    with pytest.raises(FrozenInstanceError):
        config.cell_scale = original_scale + 1

    overridden = replace(config, cell_scale=original_scale + 1)
    assert overridden.cell_scale == original_scale + 1
    assert config.cell_scale == original_scale


@pytest.mark.parametrize(
    "field",
    [
        "default_grid_width",
        "default_grid_height",
        "max_grid_width",
        "max_grid_height",
        "cell_scale",
        "symbols_per_world",
        "max_buffered_turns",
        "side_panel_width",
        "min_game_width",
        "min_game_height",
    ],
)
def test_integer_fields_must_be_positive(field: str) -> None:
    """Every dimension/count/scale setting rejects zero consistently."""
    with pytest.raises(ValueError, match=rf"{field} must be at least 1"):
        GameConfig(**{field: 0})


@pytest.mark.parametrize("value", [1.5, "2", True, None])
def test_integer_fields_reject_non_integers(value: object) -> None:
    """Booleans and coercible-looking values are not silently accepted."""
    with pytest.raises(ValueError, match="cell_scale must be an integer"):
        GameConfig(cell_scale=value)


@pytest.mark.parametrize("value", ["stretch", 1, None, ["cap"]])
def test_sizing_mode_has_two_explicit_choices(value: object) -> None:
    with pytest.raises(ValueError, match="sizing_mode must be 'cap' or 'fill'"):
        GameConfig(sizing_mode=value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("initial_speed_interval", 0),
        ("initial_speed_interval", -0.1),
        ("initial_speed_interval", math.inf),
        ("initial_speed_interval", math.nan),
        ("min_speed_interval", 0),
        ("min_speed_interval", math.inf),
        ("speed_increase_factor", 0),
        ("speed_increase_factor", math.nan),
    ],
)
def test_speed_numbers_must_be_finite_and_positive(field: str, value: float) -> None:
    with pytest.raises(ValueError, match=rf"{field} must be finite and greater than 0"):
        GameConfig(**{field: value})


def test_initial_speed_cannot_exceed_safety_cap() -> None:
    """An interval below the floor is rejected instead of silently corrected."""
    with pytest.raises(
        ValueError,
        match="initial_speed_interval must be greater than or equal to min_speed_interval",
    ):
        GameConfig(initial_speed_interval=0.001, min_speed_interval=0.002)


def test_speed_factor_cannot_slow_the_game_after_food() -> None:
    with pytest.raises(
        ValueError, match="speed_increase_factor must be less than or equal to 1"
    ):
        GameConfig(speed_increase_factor=1.01)


@pytest.mark.parametrize("field", ["max_grid_width", "max_grid_height"])
def test_grid_cap_cannot_be_below_layout_minimum(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        GameConfig(**{field: 9})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("snake_block", "█", "exactly 2 terminal cells"),
        ("snake_block", 2, "must be a string"),
        ("empty_cell", " ", "exactly 2 terminal cells"),
        ("empty_cell", None, "must be a string"),
    ],
)
def test_render_cells_have_stable_terminal_width(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        GameConfig(**{field: value})


def test_food_sprite_flag_is_boolean() -> None:
    with pytest.raises(ValueError, match="food_sprites must be a boolean"):
        GameConfig(food_sprites=1)


def test_valid_boundary_values_are_accepted() -> None:
    """Minimum counts, a 1x2 model default, and equal speed floor are coherent."""
    config = GameConfig(
        default_grid_width=1,
        default_grid_height=2,
        cell_scale=1,
        initial_speed_interval=0.002,
        min_speed_interval=0.002,
        speed_increase_factor=1,
        symbols_per_world=1,
        max_buffered_turns=1,
        side_panel_width=1,
    )
    assert (config.default_grid_width, config.default_grid_height) == (1, 2)
