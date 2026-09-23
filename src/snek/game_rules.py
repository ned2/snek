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
    def direction_between(
        start: Position, end: Position, width: int, height: int
    ) -> Direction | None:
        """The direction of a one-cell move from `start` to `end`, if adjacent.

        Wrap-aware: a move across the seam (e.g. x = width - 1 to x = 0) reads
        as continuing in the same direction, not as a jump back across the board.
        Returns None for cells that are not adjacent.
        """
        dx = (end[0] - start[0]) % width
        dy = (end[1] - start[1]) % height
        if dy == 0 and dx == 1:
            return Direction.RIGHT
        if dy == 0 and dx == width - 1 and dx != 0:
            return Direction.LEFT
        if dx == 0 and dy == 1:
            return Direction.DOWN
        if dx == 0 and dy == height - 1 and dy != 0:
            return Direction.UP
        return None

    @staticmethod
    def is_self_collision(head: Position, body: list[Position]) -> bool:
        """Check if the head collides with the body."""
        return head in body

    @staticmethod
    def is_food_collision(head: Position, food: Position) -> bool:
        """Check if the head collides with food."""
        return head == food
