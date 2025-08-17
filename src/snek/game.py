import random

from .config import GameConfig, default_config
from .game_rules import Direction, GameRules, Position
from .unicode_journey import WorldPath


class Game:
    def __init__(
        self,
        width: int = None,
        height: int = None,
        config: GameConfig = None,
        rng: random.Random = None,
    ) -> None:
        self.config = config or default_config
        self.width = width or self.config.default_grid_width
        self.height = height or self.config.default_grid_height
        self.rng = rng or random.Random()

        self.world_path = WorldPath(
            levels_per_world=self.config.levels_per_unicode_phase
        )
        self.reset()

    def reset(self) -> None:
        mid = (self.width // 2, self.height // 2)
        self.snake: list[Position] = [mid]
        self.direction = Direction.RIGHT
        self.symbols_consumed = 0
        self.level = 1
        self.current_color = self.config.default_color
        self.initial_interval = self.config.initial_speed_interval
        self.current_interval = self.initial_interval
        self.place_food()
        self.game_over = False
        self.paused = False

    def place_food(self) -> None:
        while True:
            p = (self.rng.randrange(self.width), self.rng.randrange(self.height))
            if p not in self.snake:
                self.food = p
                self.food_emoji = self.world_path.get_food_character(self.level)
                return

    def turn(self, dir: Direction) -> None:
        if GameRules.is_valid_turn(self.direction, dir):
            self.direction = dir

    def step(self) -> None:
        if self.game_over or self.paused:
            return

        # Calculate new head position
        new_head = GameRules.calculate_new_position(
            self.snake[0], self.direction, self.width, self.height
        )

        # Check for self collision
        if GameRules.is_self_collision(new_head, self.snake):
            self.game_over = True
            return

        # Move snake
        self.snake.insert(0, new_head)

        # Check for food collision
        if GameRules.is_food_collision(new_head, self.food):
            self.symbols_consumed += 1
            self.check_level_up()
            self.place_food()
        else:
            self.snake.pop()

    def check_level_up(self) -> None:
        """Check if player should level up and update color to new color."""
        if GameRules.should_level_up(
            self.symbols_consumed, self.level, self.config.symbols_per_level
        ):
            self.level += 1
            available_colors = [
                c for c in self.config.level_colors if c != self.current_color
            ]
            self.current_color = self.rng.choice(available_colors)

    def update_speed(self, new_interval: float) -> None:
        """Update the current speed interval."""
        self.current_interval = new_interval

    def get_moves_per_second(self) -> float:
        """Get current speed as moves per second."""
        return 1.0 / self.current_interval

    def resize(self, new_width: int, new_height: int) -> None:
        """Resize grid and scale snake and food positions."""
        old_width, old_height = self.width, self.height
        # Scale snake positions
        self.snake = [
            GameRules.scale_position(pos, old_width, old_height, new_width, new_height)
            for pos in self.snake
        ]
        # Scale food position
        self.food = GameRules.scale_position(
            self.food, old_width, old_height, new_width, new_height
        )
        self.width, self.height = new_width, new_height

    @property
    def is_running(self) -> bool:
        """Check if game is in a running state."""
        return not self.game_over and not self.paused

    @property
    def state(self) -> dict:
        """Get game state for testing."""
        return {
            "snake_length": len(self.snake),
            "score": self.symbols_consumed,
            "level": self.level,
            "game_over": self.game_over,
            "paused": self.paused,
            "direction": self.direction,
            "food_position": self.food,
            "head_position": self.snake[0] if self.snake else None,
        }

    def set_snake_position(self, positions: list[Position]) -> None:
        """Set snake position for testing."""
        if not positions:
            raise ValueError("Snake must have at least one position")
        self.snake = positions

    def set_food_position(self, position: Position, emoji: str = None) -> None:
        """Set food position for testing."""
        if position[0] >= self.width or position[1] >= self.height:
            raise ValueError(f"Food position {position} is out of bounds")
        self.food = position
        self.food_emoji = emoji or self.world_path.get_food_character(self.level)
