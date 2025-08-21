"""Core game logic and state management for Snek."""

import random

from .config import GameConfig, default_config
from .game_rules import Direction, GameRules, Position
from .worlds import WorldPath


class Game:
    """Game engine that manages snake movement, food placement, and world progression."""

    def __init__(
        self,
        width: int = None,
        height: int = None,
        config: GameConfig = None,
        rng: random.Random = None,
    ) -> None:
        """Initialize a new game with given dimensions and configuration."""
        self.config = config or default_config
        self.width = width or self.config.default_grid_width
        self.height = height or self.config.default_grid_height
        self.rng = rng or random.Random()

        self.world_path = WorldPath()
        self.reset()

    def reset(self) -> None:
        """Reset the game to initial state with snake at center."""
        mid = (self.width // 2, self.height // 2)
        self.snake: list[Position] = [mid]
        self.direction = Direction.RIGHT
        self.symbols_consumed = 0
        self.current_world = 0
        self.symbols_in_current_world = 0
        self.initial_interval = self.config.initial_speed_interval
        self.current_interval = self.initial_interval
        self.game_over = False
        self.paused = False
        self.place_food()

    def place_food(self) -> None:
        """Place food at a random empty position on the grid."""
        while True:
            pos = (self.rng.randrange(self.width), self.rng.randrange(self.height))
            if pos not in self.snake:
                self.food = pos
                self.food_emoji = self.world_path.get_food_character(self.current_world)
                return

    def turn(self, new_direction: Direction) -> None:
        """Change snake direction if the turn is valid (not reversing)."""
        if GameRules.is_valid_turn(self.direction, new_direction):
            self.direction = new_direction

    def step(self) -> None:
        """Advance the game by one step: move snake, check collisions, handle food."""
        if self.game_over or self.paused:
            return
        new_head_pos = GameRules.calculate_new_position(
            self.snake[0], self.direction, self.width, self.height
        )
        grows = GameRules.is_food_collision(new_head_pos, self.food)
        # Only include the tail in collision check if we grow this turn
        body_to_check = self.snake if grows else self.snake[:-1]
        if GameRules.is_self_collision(new_head_pos, body_to_check):
            self.game_over = True
            return

        self.snake.insert(0, new_head_pos)
        if grows:
            self.symbols_consumed += 1
            self.symbols_in_current_world += 1
            self.check_world_transition()
            self.place_food()
        else:
            self.snake.pop()

    def check_world_transition(self) -> None:
        """Check if player should move to next world."""
        if self.symbols_in_current_world >= self.config.symbols_per_world:
            self.current_world += 1
            self.symbols_in_current_world = 0

    def update_speed(self, new_interval: float) -> None:
        """Update the current speed interval."""
        self.current_interval = new_interval

    def get_moves_per_second(self) -> float:
        """Get current speed as moves per second."""
        return 1.0 / self.current_interval

    def resize(self, new_width: int, new_height: int) -> None:
        """Resize grid and scale snake and food positions."""
        old_width, old_height = self.width, self.height
        self.snake = [
            GameRules.scale_position(pos, old_width, old_height, new_width, new_height)
            for pos in self.snake
        ]
        self.food = GameRules.scale_position(
            self.food, old_width, old_height, new_width, new_height
        )
        self.width, self.height = new_width, new_height

    @property
    def is_running(self) -> bool:
        """Check if game is in a running state."""
        return not self.game_over and not self.paused

    def _is_valid_position(self, position: Position) -> bool:
        """Check if a position is within grid bounds."""
        x, y = position
        return 0 <= x < self.width and 0 <= y < self.height

    def set_snake_position(self, positions: list[Position]) -> None:
        """Set snake position for testing."""
        if not positions:
            raise ValueError("Snake must have at least one position")
        for pos in positions:
            if not self._is_valid_position(pos):
                raise ValueError(f"Snake position {pos} is out of bounds")
        self.snake = positions

    def set_food_position(self, position: Position, emoji: str = None) -> None:
        """Set food position for testing."""
        if not self._is_valid_position(position):
            raise ValueError(f"Food position {position} is out of bounds")
        self.food = position
        self.food_emoji = emoji or self.world_path.get_food_character(
            self.current_world
        )
