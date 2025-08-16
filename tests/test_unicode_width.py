"""Test to ensure all food characters have single column width."""

import pytest
from rich.cells import cell_len

from snek.unicode_journey import WorldPath


def test_all_food_characters_single_width():
    """Ensure all food characters have single column width for safe grid rendering."""
    world_path = WorldPath()
    
    # Collect all unique food characters from all worlds
    all_food_chars = set()
    for world in world_path.worlds:
        all_food_chars.update(world.characters)
    
    # Check each character
    invalid_chars = []
    for char in all_food_chars:
        width = cell_len(char)
        if width != 1:
            invalid_chars.append((char, width))
    
    # Assert no invalid characters found
    assert len(invalid_chars) == 0, (
        f"Found {len(invalid_chars)} food characters with non-single column width:\n" +
        "\n".join([f"  '{char}' has width {width}" for char, width in invalid_chars])
    )


def test_food_character_per_level():
    """Test that we can get a valid single-width food character for each level."""
    world_path = WorldPath()
    
    # Test first 50 levels (should cover multiple worlds)
    for level in range(1, 51):
        food_char = world_path.get_food_character(level)
        width = cell_len(food_char)
        assert width == 1, f"Level {level} food character '{food_char}' has width {width}, expected 1"
