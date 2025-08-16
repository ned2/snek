"""Unit tests for game rules and logic."""
import pytest
from snek.game_rules import Direction, GameRules, Position


class TestDirection:
    """Test Direction enum and related operations."""
    
    def test_opposite_directions(self):
        """Test getting opposite directions."""
        assert GameRules.get_opposite_direction(Direction.UP) == Direction.DOWN
        assert GameRules.get_opposite_direction(Direction.DOWN) == Direction.UP
        assert GameRules.get_opposite_direction(Direction.LEFT) == Direction.RIGHT
        assert GameRules.get_opposite_direction(Direction.RIGHT) == Direction.LEFT
    
    def test_valid_turns(self):
        """Test valid turn detection."""
        # Valid turns (perpendicular directions)
        assert GameRules.is_valid_turn(Direction.UP, Direction.LEFT) is True
        assert GameRules.is_valid_turn(Direction.UP, Direction.RIGHT) is True
        assert GameRules.is_valid_turn(Direction.DOWN, Direction.LEFT) is True
        assert GameRules.is_valid_turn(Direction.DOWN, Direction.RIGHT) is True
        assert GameRules.is_valid_turn(Direction.LEFT, Direction.UP) is True
        assert GameRules.is_valid_turn(Direction.LEFT, Direction.DOWN) is True
        assert GameRules.is_valid_turn(Direction.RIGHT, Direction.UP) is True
        assert GameRules.is_valid_turn(Direction.RIGHT, Direction.DOWN) is True
        
        # Invalid turns (opposite directions)
        assert GameRules.is_valid_turn(Direction.UP, Direction.DOWN) is False
        assert GameRules.is_valid_turn(Direction.DOWN, Direction.UP) is False
        assert GameRules.is_valid_turn(Direction.LEFT, Direction.RIGHT) is False
        assert GameRules.is_valid_turn(Direction.RIGHT, Direction.LEFT) is False
        
        # Same direction is valid
        assert GameRules.is_valid_turn(Direction.UP, Direction.UP) is True


class TestPositionCalculation:
    """Test position calculation and movement."""
    
    def test_calculate_new_position_normal(self):
        """Test normal movement without wrapping."""
        # Moving up
        assert GameRules.calculate_new_position((5, 5), Direction.UP, 10, 10) == (5, 4)
        # Moving down
        assert GameRules.calculate_new_position((5, 5), Direction.DOWN, 10, 10) == (5, 6)
        # Moving left
        assert GameRules.calculate_new_position((5, 5), Direction.LEFT, 10, 10) == (4, 5)
        # Moving right
        assert GameRules.calculate_new_position((5, 5), Direction.RIGHT, 10, 10) == (6, 5)
    
    def test_calculate_new_position_wrapping(self):
        """Test position wrapping at boundaries."""
        # Wrap from top to bottom
        assert GameRules.calculate_new_position((5, 0), Direction.UP, 10, 10) == (5, 9)
        # Wrap from bottom to top
        assert GameRules.calculate_new_position((5, 9), Direction.DOWN, 10, 10) == (5, 0)
        # Wrap from left to right
        assert GameRules.calculate_new_position((0, 5), Direction.LEFT, 10, 10) == (9, 5)
        # Wrap from right to left
        assert GameRules.calculate_new_position((9, 5), Direction.RIGHT, 10, 10) == (0, 5)
    
    def test_scale_position(self):
        """Test position scaling when resizing."""
        # Scale up
        assert GameRules.scale_position((5, 5), 10, 10, 20, 20) == (10, 10)
        # Scale down
        assert GameRules.scale_position((10, 10), 20, 20, 10, 10) == (5, 5)
        # Non-uniform scaling
        assert GameRules.scale_position((5, 5), 10, 10, 20, 10) == (10, 5)
        # Edge cases
        assert GameRules.scale_position((0, 0), 10, 10, 20, 20) == (0, 0)
        assert GameRules.scale_position((9, 9), 10, 10, 20, 20) == (18, 18)


class TestCollisionDetection:
    """Test collision detection logic."""
    
    def test_self_collision(self):
        """Test snake self-collision detection."""
        # No collision - head not in body
        assert GameRules.is_self_collision((5, 5), [(4, 5), (3, 5), (2, 5)]) is False
        # Collision - head hits body
        assert GameRules.is_self_collision((4, 5), [(4, 5), (3, 5), (2, 5)]) is True
        # Empty body
        assert GameRules.is_self_collision((5, 5), []) is False
    
    def test_food_collision(self):
        """Test food collision detection."""
        # Collision
        assert GameRules.is_food_collision((5, 5), (5, 5)) is True
        # No collision
        assert GameRules.is_food_collision((5, 5), (5, 6)) is False
        assert GameRules.is_food_collision((5, 5), (6, 5)) is False


class TestLevelProgression:
    """Test level progression logic."""
    
    def test_should_level_up(self):
        """Test level up conditions."""
        # Level 1 -> 2 (after 5 symbols)
        assert GameRules.should_level_up(4, 1, 5) is False
        assert GameRules.should_level_up(5, 1, 5) is True
        
        # Level 2 -> 3 (after 10 symbols total)
        assert GameRules.should_level_up(9, 2, 5) is False
        assert GameRules.should_level_up(10, 2, 5) is True
        
        # Level 3 -> 4 (after 15 symbols total)
        assert GameRules.should_level_up(14, 3, 5) is False
        assert GameRules.should_level_up(15, 3, 5) is True
