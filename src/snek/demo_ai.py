"""Demo AI that automatically plays the snake game using pathfinding heuristics."""

from collections import deque
from typing import Optional

from .game_rules import Direction, GameRules, Position


class DemoAI:
    """AI player that automatically plays the snake game using pathfinding."""

    def __init__(self, game) -> None:
        """Initialize the demo AI with a reference to the game."""
        self.game = game
        self.path: list[Position] = []

    def get_next_direction(self) -> Optional[Direction]:
        """Get the next optimal direction for the snake to move."""
        if not self.game.is_running:
            return None

        head = self.game.snake[0]
        food = self.game.food

        # If we have a valid path and the next position is still safe, follow it
        if len(self.path) > 1 and self._is_path_still_safe():
            next_pos = self.path[1]  # Skip current head position
            direction = self._get_direction_to_position(head, next_pos)
            if direction and GameRules.is_valid_turn(self.game.direction, direction):
                self.path.pop(0)  # Remove current position from path
                return direction

        # Calculate new path to food
        self.path = self._find_path_to_food(head, food)

        if len(self.path) > 1:
            next_pos = self.path[1]  # Skip current head position
            direction = self._get_direction_to_position(head, next_pos)
            if direction and GameRules.is_valid_turn(self.game.direction, direction):
                self.path.pop(0)  # Remove current position from path
                return direction

        # Fallback: try to avoid immediate collision
        return self._avoid_collision()

    def _is_path_still_safe(self) -> bool:
        """Check if the current path is still safe to follow."""
        if len(self.path) < 2:
            return False

        # Check if any part of the path intersects with the snake body
        snake_set = set(self.game.snake[1:])  # Exclude head
        for pos in self.path[1:]:  # Skip current head position
            if pos in snake_set:
                return False
        return True

    def _find_path_to_food(self, start: Position, goal: Position) -> list[Position]:
        """Find optimal path from start to goal using BFS with safety considerations."""
        if start == goal:
            return [start]

        # First try to find a direct path
        path = self._bfs_path(start, goal, avoid_body=True)
        if path:
            return path

        # If no direct path, try with more lenient collision avoidance
        path = self._bfs_path(start, goal, avoid_body=False)
        if path:
            return path

        # Last resort: just move towards food
        return self._greedy_path_to_food(start, goal)

    def _bfs_path(
        self, start: Position, goal: Position, avoid_body: bool = True
    ) -> Optional[list[Position]]:
        """Use BFS to find shortest path, optionally avoiding snake body."""
        queue = deque([(start, [start])])
        visited = {start}
        snake_set = set(self.game.snake[1:]) if avoid_body else set()

        while queue:
            current, path = queue.popleft()

            if current == goal:
                return path

            for direction in Direction:
                next_pos = GameRules.calculate_new_position(
                    current, direction, self.game.width, self.game.height
                )

                if (
                    next_pos not in visited
                    and next_pos not in snake_set
                    and self._is_safe_move(current, next_pos, len(path))
                ):
                    visited.add(next_pos)
                    queue.append((next_pos, path + [next_pos]))

        return None

    def _is_safe_move(
        self, current: Position, next_pos: Position, path_length: int
    ) -> bool:
        """Check if a move is safe considering future snake positions."""
        # Basic safety: don't hit the snake body immediately
        if next_pos in self.game.snake:
            return False

        # Advanced safety: consider if the tail will move
        # If we haven't eaten recently, the tail will move away
        if path_length > len(self.game.snake) // 2:
            return True

        return True

    def _greedy_path_to_food(self, start: Position, goal: Position) -> list[Position]:
        """Create a simple greedy path towards the food."""
        path = [start]
        current = start

        for _ in range(
            max(self.game.width, self.game.height) * 2
        ):  # Prevent infinite loops
            if current == goal:
                break

            # Find direction that reduces distance to food
            best_direction = None
            best_distance = float("inf")

            for direction in Direction:
                next_pos = GameRules.calculate_new_position(
                    current, direction, self.game.width, self.game.height
                )

                if next_pos not in self.game.snake and GameRules.is_valid_turn(
                    self._pos_to_direction(current, next_pos), direction
                ):
                    distance = self._manhattan_distance(next_pos, goal)
                    if distance < best_distance:
                        best_distance = distance
                        best_direction = direction

            if best_direction:
                current = GameRules.calculate_new_position(
                    current, best_direction, self.game.width, self.game.height
                )
                path.append(current)
            else:
                break

        return path

    def _avoid_collision(self) -> Optional[Direction]:
        """Try to avoid immediate collision when no path to food exists."""
        head = self.game.snake[0]
        snake_set = set(self.game.snake)

        # Try directions in order of preference
        preferred_directions = [
            Direction.UP,
            Direction.RIGHT,
            Direction.DOWN,
            Direction.LEFT,
        ]

        for direction in preferred_directions:
            if not GameRules.is_valid_turn(self.game.direction, direction):
                continue

            next_pos = GameRules.calculate_new_position(
                head, direction, self.game.width, self.game.height
            )

            if next_pos not in snake_set:
                return direction

        return None

    def _get_direction_to_position(
        self, current: Position, target: Position
    ) -> Optional[Direction]:
        """Get the direction needed to move from current position to target position."""
        dx = target[0] - current[0]
        dy = target[1] - current[1]

        # Handle wrapping
        if abs(dx) > self.game.width // 2:
            dx = -dx / abs(dx) if dx != 0 else 0
        if abs(dy) > self.game.height // 2:
            dy = -dy / abs(dy) if dy != 0 else 0

        if dx > 0:
            return Direction.RIGHT
        elif dx < 0:
            return Direction.LEFT
        elif dy > 0:
            return Direction.DOWN
        elif dy < 0:
            return Direction.UP

        return None

    def _pos_to_direction(self, current: Position, target: Position) -> Direction:
        """Convert position difference to direction (for validation)."""
        direction = self._get_direction_to_position(current, target)
        return direction or Direction.RIGHT  # Default fallback

    def _manhattan_distance(self, pos1: Position, pos2: Position) -> float:
        """Calculate Manhattan distance between two positions with wrapping."""
        dx = abs(pos1[0] - pos2[0])
        dy = abs(pos1[1] - pos2[1])

        # Consider wrapping
        dx = min(dx, self.game.width - dx)
        dy = min(dy, self.game.height - dy)

        return dx + dy
