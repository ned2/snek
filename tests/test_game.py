"""Unit tests for the Game class."""

import pytest

from snek.game import Game
from snek.game_rules import Direction


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
        game.game_over = True
        game.snake = [(1, 1), (2, 1), (3, 1)]

        # Reset
        game.reset()

        # Check reset state
        assert game.symbols_consumed == 0
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
        # Create a snake that will collide with its body (not tail)
        # Snake body: head -> (5,5) -> (4,5) -> (4,4) -> (5,4) -> tail (6,4)
        game.snake = [(5, 5), (4, 5), (4, 4), (5, 4), (6, 4)]
        game.direction = Direction.UP  # Will hit (5, 4) which is part of body

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
        """Test resize preserves symbols consumed and current world."""
        game = Game()
        game.symbols_consumed = 10
        game.current_world = 3

        game.resize(30, 30)

        assert game.symbols_consumed == 10
        assert game.current_world == 3

    def test_set_food_position_validation(self):
        """Test food position validation with bounds checking."""
        game = Game(width=10, height=10)

        # Valid positions should work
        game.set_food_position((5, 5))
        assert game.food == (5, 5)

        game.set_food_position((0, 0))  # Lower bound
        assert game.food == (0, 0)

        game.set_food_position((9, 9))  # Upper bound
        assert game.food == (9, 9)

        # Invalid positions should raise ValueError
        with pytest.raises(ValueError, match="Food position .* is out of bounds"):
            game.set_food_position((-1, 5))  # Negative x

        with pytest.raises(ValueError, match="Food position .* is out of bounds"):
            game.set_food_position((5, -1))  # Negative y

        with pytest.raises(ValueError, match="Food position .* is out of bounds"):
            game.set_food_position((10, 5))  # x >= width

        with pytest.raises(ValueError, match="Food position .* is out of bounds"):
            game.set_food_position((5, 10))  # y >= height

    def test_set_snake_position_validation(self):
        """Test snake position validation with bounds checking."""
        game = Game(width=10, height=10)

        # Valid positions should work
        game.set_snake_position([(5, 5), (4, 5), (3, 5)])
        assert game.snake == [(5, 5), (4, 5), (3, 5)]

        # Empty snake should raise ValueError
        with pytest.raises(ValueError, match="Snake must have at least one position"):
            game.set_snake_position([])

        # Out of bounds positions should raise ValueError
        with pytest.raises(ValueError, match="Snake position .* is out of bounds"):
            game.set_snake_position([(-1, 5)])  # Negative x

        with pytest.raises(ValueError, match="Snake position .* is out of bounds"):
            game.set_snake_position([(5, -1)])  # Negative y

        with pytest.raises(ValueError, match="Snake position .* is out of bounds"):
            game.set_snake_position([(10, 5)])  # x >= width

        with pytest.raises(ValueError, match="Snake position .* is out of bounds"):
            game.set_snake_position([(5, 10)])  # y >= height

        # Multiple positions with one invalid should raise error
        with pytest.raises(ValueError, match="Snake position .* is out of bounds"):
            game.set_snake_position([(5, 5), (4, 5), (-1, 5)])

    def test_is_valid_position_helper(self):
        """Test the internal position validation helper."""
        game = Game(width=10, height=10)

        # Valid positions
        assert game._is_valid_position((0, 0)) is True
        assert game._is_valid_position((5, 5)) is True
        assert game._is_valid_position((9, 9)) is True

        # Invalid positions
        assert game._is_valid_position((-1, 5)) is False
        assert game._is_valid_position((5, -1)) is False
        assert game._is_valid_position((10, 5)) is False
        assert game._is_valid_position((5, 10)) is False
