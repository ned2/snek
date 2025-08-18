"""Game rules and logic separated from state management."""

from enum import Enum, auto


Position = tuple[int, int]


class Direction(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()


class GameRules:
    """Pure game logic and rules, separated from state."""

    @staticmethod
    def get_opposite_direction(direction: Direction) -> Direction:
        """Get the opposite direction."""
        opposites = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT,
        }
        return opposites[direction]

    @staticmethod
    def is_valid_turn(current: Direction, new: Direction) -> bool:
        """Check if a turn is valid (not reversing into itself)."""
        return new != GameRules.get_opposite_direction(current)

    @staticmethod
    def calculate_new_position(
        head: Position, direction: Direction, width: int, height: int
    ) -> Position:
        """Calculate new head position based on direction, with wrapping."""
        delta = {
            Direction.UP: (0, -1),
            Direction.DOWN: (0, 1),
            Direction.LEFT: (-1, 0),
            Direction.RIGHT: (1, 0),
        }[direction]

        new_x = (head[0] + delta[0]) % width
        new_y = (head[1] + delta[1]) % height
        return (new_x, new_y)

    @staticmethod
    def is_self_collision(head: Position, body: list[Position]) -> bool:
        """Check if the head collides with the body."""
        return head in body

    @staticmethod
    def is_food_collision(head: Position, food: Position) -> bool:
        """Check if the head collides with food."""
        return head == food

    @staticmethod
    def scale_position(
        pos: Position, old_width: int, old_height: int, new_width: int, new_height: int
    ) -> Position:
        """Scale a position from old dimensions to new dimensions."""
        scaled_x = min(int(pos[0] * new_width / old_width), new_width - 1)
        scaled_y = min(int(pos[1] * new_height / old_height), new_height - 1)
        return (scaled_x, scaled_y)
