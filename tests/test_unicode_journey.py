"""Tests for world path functionality."""
import pytest
from snek.unicode_journey import WorldPath, World


class TestWorld:
    """Test World dataclass."""
    
    def test_world_creation(self):
        """Test creating a world."""
        world = World(
            name="Test World",
            description="A test world",
            characters=["A", "B", "C"]
        )
        
        assert world.name == "Test World"
        assert world.description == "A test world"
        assert world.characters == ["A", "B", "C"]


class TestWorldPath:
    """Test WorldPath class."""
    
    def test_initialization(self):
        """Test world path initialization."""
        journey = WorldPath(levels_per_world=2)
        
        assert journey.levels_per_world == 2
        assert len(journey.worlds) > 0
        assert journey.worlds[0].name == "Basic Symbols"
    
    def test_get_world_for_level(self):
        """Test getting world for different levels."""
        journey = WorldPath(levels_per_world=2)
        
        # Levels 1-2 should be Basic Symbols
        assert journey.get_world_for_level(1).name == "Basic Symbols"
        assert journey.get_world_for_level(2).name == "Basic Symbols"
        
        # Levels 3-4 should be Ancient Egypt
        assert journey.get_world_for_level(3).name == "Ancient Egypt"
        assert journey.get_world_for_level(4).name == "Ancient Egypt"
        
        # Levels 5-6 should be Classical Greece
        assert journey.get_world_for_level(5).name == "Classical Greece"
    
    def test_get_food_character(self):
        """Test getting food characters."""
        journey = WorldPath(levels_per_world=2)
        
        # Get characters for level 1
        chars_level_1 = set()
        for _ in range(10):  # Get 10 characters
            char = journey.get_food_character(1)
            chars_level_1.add(char)
            assert char in journey.worlds[0].characters
        
        # Should have gotten multiple different characters
        assert len(chars_level_1) > 1
    
    def test_character_pool_refill(self):
        """Test that character pool refills when exhausted."""
        journey = WorldPath(levels_per_world=2)
        world = journey.worlds[0]
        
        # Exhaust all characters
        chars_seen = []
        for _ in range(len(world.characters) + 5):  # More than available
            char = journey.get_food_character(1)
            chars_seen.append(char)
            assert char in world.characters
        
        # Should have seen all characters
        assert set(chars_seen[:len(world.characters)]) == set(world.characters)
    
    def test_is_new_world(self):
        """Test detecting new world transitions."""
        journey = WorldPath(levels_per_world=2)
        
        assert not journey.is_new_world(1)  # First level
        assert not journey.is_new_world(2)  # Same world
        assert journey.is_new_world(3)      # New world
        assert not journey.is_new_world(4)  # Same world
        assert journey.is_new_world(5)      # New world
    
    def test_world_names_and_descriptions(self):
        """Test getting world names and descriptions."""
        journey = WorldPath(levels_per_world=2)
        
        assert journey.get_world_name(1) == "Basic Symbols"
        assert "Simple geometric" in journey.get_world_description(1)
        
        assert journey.get_world_name(3) == "Ancient Egypt"
        assert "Hieroglyphic" in journey.get_world_description(3)
    
    def test_custom_levels_per_world(self):
        """Test with different levels per world."""
        journey = WorldPath(levels_per_world=3)
        
        # With 3 levels per world
        assert journey.get_world_for_level(1).name == "Basic Symbols"
        assert journey.get_world_for_level(3).name == "Basic Symbols"
        assert journey.get_world_for_level(4).name == "Ancient Egypt"
        assert journey.get_world_for_level(6).name == "Ancient Egypt"
        assert journey.get_world_for_level(7).name == "Classical Greece"
    
    def test_world_progression_order(self):
        """Test that worlds progress in the expected order."""
        journey = WorldPath(levels_per_world=1)
        
        expected_order = [
            "Basic Symbols",
            "Ancient Egypt",
            "Classical Greece",
            "Norse Runes",
            "Alchemical Mysteries",
            "Mathematical Realm",
            "Global Currencies",
            "Digital Age"
        ]
        
        for i, expected_name in enumerate(expected_order, 1):
            assert journey.get_world_name(i) == expected_name
    
    def test_world_wrap_around(self):
        """Test that worlds wrap around after the last one."""
        journey = WorldPath(levels_per_world=1)
        
        # Test wrap around - level 9 should go back to Basic Symbols
        assert journey.get_world_name(9) == "Basic Symbols"
        assert journey.get_world_name(10) == "Ancient Egypt"
        
        # Test with different levels per world
        journey2 = WorldPath(levels_per_world=2)
        # 8 worlds * 2 levels = 16 levels to complete all worlds
        # Level 17 should wrap to Basic Symbols
        assert journey2.get_world_name(17) == "Basic Symbols"
        assert journey2.get_world_name(19) == "Ancient Egypt"
