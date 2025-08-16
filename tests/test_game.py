"""Unit tests for the Game class."""
import pytest
import random
from snek.game import Game
from snek.game_rules import Direction
from snek.config import GameConfig


class TestGameInitialization:
    """Test game initialization and reset."""
    
    def test_default_initialization(self):
        """Test game initializes with default values."""
        game = Game()
        assert game.width == game.config.default_grid_width
        assert game.height == game.config.default_grid_height
        assert len(game.snake) == 1
        assert game.snake[0] == (game.width // 2, game.height // 2)
        assert game.direction == Direction.RIGHT
        assert game.symbols_consumed == 0
        assert game.level == 1
        assert game.game_over is False
        assert game.paused is False
    
    def test_custom_dimensions(self):
        """Test game with custom dimensions."""
        game = Game(width=30, height=20)
        assert game.width == 30
        assert game.height == 20
        assert game.snake[0] == (15, 10)  # Center position
    
    def test_reset(self):
        """Test game reset functionality."""
        game = Game()
        # Modify game state
        game.symbols_consumed = 100
        game.level = 5
        game.game_over = True
        game.snake = [(1, 1), (2, 1), (3, 1)]
        
        # Reset
        game.reset()
        
        # Check reset state
        assert game.symbols_consumed == 0
        assert game.level == 1
        assert game.game_over is False
        assert len(game.snake) == 1
        assert game.snake[0] == (game.width // 2, game.height // 2)


class TestFoodPlacement:
    """Test food placement logic."""
    
    def test_place_food(self):
        """Test food is placed in valid position."""
        game = Game(width=10, height=10)
        
        # Food should not be on snake
        assert game.food not in game.snake
        
        # Food should be within bounds
        assert 0 <= game.food[0] < game.width
        assert 0 <= game.food[1] < game.height
    
    def test_place_food_with_long_snake(self):
        """Test food placement when snake occupies many cells."""
        game = Game(width=5, height=5)
        # Fill most of the grid with snake
        game.snake = [(x, y) for x in range(5) for y in range(4)]
        
        # Place new food
        game.place_food()
        
        # Food should be in one of the remaining cells
        assert game.food not in game.snake
        assert game.food[1] == 4  # Only row 4 is free


class TestMovement:
    """Test snake movement mechanics."""
    
    def test_turn_valid(self):
        """Test valid turn changes direction."""
        game = Game()
        game.direction = Direction.RIGHT
        
        game.turn(Direction.UP)
        assert game.direction == Direction.UP
        
        game.turn(Direction.LEFT)
        assert game.direction == Direction.LEFT
    
    def test_turn_invalid(self):
        """Test invalid turn is ignored."""
        game = Game()
        game.direction = Direction.RIGHT
        
        # Can't turn to opposite direction
        game.turn(Direction.LEFT)
        assert game.direction == Direction.RIGHT
        
        # But can turn perpendicular
        game.turn(Direction.UP)
        assert game.direction == Direction.UP
    
    def test_step_normal_movement(self):
        """Test normal snake movement."""
        game = Game()
        initial_head = game.snake[0]
        
        game.step()
        
        # Head moved right
        assert game.snake[0] == (initial_head[0] + 1, initial_head[1])
        # Still length 1
        assert len(game.snake) == 1
    
    def test_step_with_food(self):
        """Test snake grows when eating food."""
        game = Game()
        # Place food right in front of snake
        game.food = (game.snake[0][0] + 1, game.snake[0][1])
        initial_length = len(game.snake)
        
        game.step()
        
        # Snake grew
        assert len(game.snake) == initial_length + 1
        # Symbols consumed increased
        assert game.symbols_consumed == 1
        # New food was placed
        assert game.food != game.snake[0]
    
    def test_step_self_collision(self):
        """Test game over on self collision."""
        game = Game()
        # Create a snake that will collide with itself
        game.snake = [(5, 5), (4, 5), (4, 4), (5, 4)]
        game.direction = Direction.UP  # Will hit (5, 4)
        
        game.step()
        
        assert game.game_over is True
    
    def test_step_when_paused(self):
        """Test no movement when paused."""
        game = Game()
        game.paused = True
        initial_position = game.snake[0]
        
        game.step()
        
        # Snake didn't move
        assert game.snake[0] == initial_position
    
    def test_step_when_game_over(self):
        """Test no movement when game over."""
        game = Game()
        game.game_over = True
        initial_position = game.snake[0]
        
        game.step()
        
        # Snake didn't move
        assert game.snake[0] == initial_position


class TestLevelProgression:
    """Test level and speed progression."""
    
    def test_check_level_up(self):
        """Test level increases at correct intervals."""
        game = Game()
        
        # Eat 4 symbols - no level up
        game.symbols_consumed = 4
        game.check_level_up()
        assert game.level == 1
        
        # Eat 5th symbol - level up
        game.symbols_consumed = 5
        game.check_level_up()
        assert game.level == 2
        
        # Level should have changed
        assert game.level == 2
    
    def test_update_speed(self):
        """Test speed update changes tick interval."""
        game = Game()
        # Store initial speed
        initial_speed = game.get_moves_per_second()
        
        # Update to faster speed
        game.update_speed(0.05)
        
        # Speed should be faster (more moves per second)
        new_speed = game.get_moves_per_second()
        assert new_speed > initial_speed
    
    def test_get_moves_per_second(self):
        """Test moves per second calculation."""
        game = Game()
        # Default speed should be positive
        assert game.get_moves_per_second() > 0
        
        # After speed update, should reflect new speed
        game.update_speed(0.1)
        # Should be approximately 10 moves per second
        assert 9.5 <= game.get_moves_per_second() <= 10.5


class TestResize:
    """Test game resizing functionality."""
    
    def test_resize_scales_positions(self):
        """Test snake and food positions scale with resize."""
        game = Game(width=10, height=10)
        game.snake = [(5, 5), (4, 5), (3, 5)]
        game.food = (7, 7)
        
        game.resize(20, 20)
        
        # Check dimensions updated
        assert game.width == 20
        assert game.height == 20
        
        # Check positions scaled
        assert game.snake == [(10, 10), (8, 10), (6, 10)]
        assert game.food == (14, 14)
    
    def test_resize_maintains_game_state(self):
        """Test resize preserves symbols consumed and level."""
        game = Game()
        game.symbols_consumed = 10
        game.level = 3
        
        game.resize(30, 30)
        
        assert game.symbols_consumed == 10
        assert game.level == 3
