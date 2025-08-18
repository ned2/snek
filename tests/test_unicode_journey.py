"""Tests for world path functionality."""

from snek.worlds import WorldPath, World
from snek.themes import THEME_MAP


class TestWorld:
    """Test World dataclass."""

    def test_world_creation(self):
        """Test creating a world."""
        world = World(
            name="Test World",
            description="A test world",
            characters=["A", "B", "C"],
            theme_name="snek-classic",
        )

        assert world.name == "Test World"
        assert world.description == "A test world"
        assert world.characters == ["A", "B", "C"]
        assert world.theme_name == "snek-classic"


class TestWorldPath:
    """Test WorldPath class."""

    def test_initialization(self):
        """Test world path initialization."""
        journey = WorldPath()

        assert len(journey.worlds) > 0
        assert journey.worlds[0].name == "Basic Symbols"
        assert journey.worlds[0].theme_name == "snek-classic"

    def test_world_theme_property(self):
        """Test that world theme property works correctly."""
        journey = WorldPath()

        # Test first world
        world = journey.get_world(0)
        assert world.theme_name in THEME_MAP
        assert world.theme == THEME_MAP[world.theme_name]
        assert world.theme.name == world.theme_name

        # Test another world
        world2 = journey.get_world(1)
        assert world2.theme_name in THEME_MAP
        assert world2.theme == THEME_MAP[world2.theme_name]

    def test_get_food_character(self):
        """Test getting food characters."""
        journey = WorldPath()

        # Get characters for world 0
        chars_world_0 = set()
        for _ in range(10):  # Get 10 characters
            char = journey.get_food_character(0)
            chars_world_0.add(char)
            assert char in journey.worlds[0].characters

        # Should have gotten multiple different characters
        assert len(chars_world_0) > 1

    def test_character_pool_refill(self):
        """Test that character pool refills when exhausted."""
        journey = WorldPath()
        world = journey.worlds[0]

        # Exhaust all characters
        chars_seen = []
        for _ in range(len(world.characters) + 5):  # More than available
            char = journey.get_food_character(0)
            chars_seen.append(char)
            assert char in world.characters

        # Should have seen all characters
        assert set(chars_seen[: len(world.characters)]) == set(world.characters)

    def test_world_names_and_descriptions(self):
        """Test getting world names and descriptions."""
        journey = WorldPath()

        assert journey.get_world_name(0) == "Basic Symbols"
        assert "Simple geometric" in journey.get_world_description(0)

        assert journey.get_world_name(1) == "Ancient Egypt"
        assert "Hieroglyphic" in journey.get_world_description(1)

    def test_world_progression_order(self):
        """Test that worlds progress in the expected order."""
        journey = WorldPath()

        expected_order = [
            "Basic Symbols",
            "Ancient Egypt",
            "Classical Greece",
            "Norse Runes",
            "Alchemical Mysteries",
            "Mathematical Realm",
            "Global Currencies",
            "Digital Age",
        ]

        for i, expected_name in enumerate(expected_order):
            assert journey.get_world_name(i) == expected_name

    def test_world_wrap_around(self):
        """Test that worlds wrap around after the last one."""
        journey = WorldPath()

        # Test wrap around - world 8 should go back to Basic Symbols
        assert journey.get_world_name(8) == "Basic Symbols"
        assert journey.get_world_name(9) == "Ancient Egypt"
