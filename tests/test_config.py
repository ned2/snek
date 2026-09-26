"""Tests for the explicit `GameConfig` validation boundary."""

from dataclasses import FrozenInstanceError, replace

import pytest

from snek.config import (
    FOOD_TYPES,
    MIN_SPRITE_SCALE,
    PALETTES,
    WORLD_CHANGES,
    GameConfig,
)
from snek.worlds import WORLD_SPEEDS


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
        "foods_per_world",
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


def test_start_world_is_one_of_the_worlds() -> None:
    for world in range(1, len(WORLD_SPEEDS) + 1):
        assert GameConfig(start_world=world).start_world == world
    for value in (0, 2.5, True):
        with pytest.raises(ValueError, match="start_world must be"):
            GameConfig(start_world=value)
    with pytest.raises(ValueError, match="start_world must be at most 9, got 10"):
        GameConfig(start_world=10)


@pytest.mark.parametrize(
    ("field", "choices"),
    [("world_change", WORLD_CHANGES), ("palette", PALETTES)],
)
def test_named_world_fields_are_one_of_their_choices(
    field: str, choices: tuple[str, ...]
) -> None:
    for choice in choices:
        assert getattr(GameConfig(**{field: choice}), field) == choice
    for value in ("sometimes", None, 1):
        with pytest.raises(ValueError, match=rf"{field} must be one of"):
            GameConfig(**{field: value})


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


def test_food_type_is_one_of_the_food_types() -> None:
    for food_type in FOOD_TYPES:
        assert GameConfig(food_type=food_type, cell_scale=2).food_type == food_type
    with pytest.raises(ValueError, match="food_type must be one of"):
        GameConfig(food_type="cake")


def test_start_length_is_a_positive_integer() -> None:
    assert GameConfig(start_length=1).start_length == 1
    for value in (0, 2.5, True):
        with pytest.raises(ValueError, match="start_length must be"):
            GameConfig(start_length=value)


def test_valid_boundary_values_are_accepted() -> None:
    """Minimum counts and a 1x2 model default are coherent."""
    config = GameConfig(
        default_grid_width=1,
        default_grid_height=2,
        cell_scale=1,
        start_world=1,
        foods_per_world=1,
        max_buffered_turns=1,
        side_panel_width=1,
    )
    assert (config.default_grid_width, config.default_grid_height) == (1, 2)


def test_smooth_motion_flag_is_boolean() -> None:
    assert GameConfig().smooth_motion is True
    with pytest.raises(ValueError, match="smooth_motion must be a boolean"):
        GameConfig(smooth_motion="no")


def test_walls_flag_is_boolean() -> None:
    assert GameConfig().walls is True  # Classic mode
    assert GameConfig(walls=False).walls is False
    with pytest.raises(ValueError, match="walls must be a boolean"):
        GameConfig(walls=1)


def test_defaults_are_nokia_style() -> None:
    """Classic, the default mode: the diamond, a length of 8, a 20x11 board, and
    a fixed world 5 on the LCD screen."""
    config = GameConfig()
    assert (config.start_world, config.world_change) == (5, "fixed")
    assert config.foods_per_world == 50
    assert config.palette == "lcd"
    assert config.food_type == "diamond"
    assert config.uses_sprites is False
    assert config.min_cell_scale == 1
    assert config.start_length == 8
    assert (config.max_grid_width, config.max_grid_height) == (20, 11)


def test_food_sprites_need_a_cell_scale_of_at_least_two() -> None:
    with pytest.raises(
        ValueError, match="food sprites need a cell scale of at least 2"
    ):
        GameConfig(food_type="sprites", cell_scale=1)
    config = GameConfig(food_type="sprites", cell_scale=MIN_SPRITE_SCALE)
    assert config.uses_sprites is True
    assert config.min_cell_scale == MIN_SPRITE_SCALE
