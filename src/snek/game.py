"""Core game logic and state management for Snek."""

from dataclasses import dataclass
import random

from .config import GameConfig, default_config, validate_dimensions
from .game_rules import Direction, GameRules, Position
from .worlds import WorldPath


@dataclass(frozen=True)
class StepResult:
    """The consequences of a single `Game.step()`, for the view to react to.

    The model owns what a tick *means* (movement, world transition, speed-up,
    game-over); the view reads these flags instead of sniffing deltas in snake
    length or world index.
    """

    moved: bool = False
    ate_food: bool = False
    world_changed: bool = False
    new_world: int | None = None
    game_over: bool = False
    won: bool = False


class Game:
    """Game engine that manages snake movement, food placement, and world progression."""

    def __init__(
        self,
        width: int | None = None,
        height: int | None = None,
        config: GameConfig | None = None,
        rng: random.Random | None = None,
    ) -> None:
        """Initialize a game with an immutable, safely shareable configuration.

        An explicitly supplied `GameConfig` is retained as-is. Omitting it uses
        the immutable module default; callers derive variants with
        `dataclasses.replace` rather than mutating either value.
        """
        self.config: GameConfig = default_config if config is None else config
        resolved_width = self.config.default_grid_width if width is None else width
        resolved_height = self.config.default_grid_height if height is None else height
        validate_dimensions(resolved_width, resolved_height)
        self.width = resolved_width
        self.height = resolved_height
        self.rng = random.Random() if rng is None else rng
        self.world_path = WorldPath(rng=self.rng)
        self.reset()

    def reset(self, *, width: int | None = None, height: int | None = None) -> None:
        """Reset the game to its initial state, optionally on a fresh grid.

        Supplying dimensions is reserved for establishing the logical grid from
        the first valid UI layout. Once play begins, viewport resizes never call
        into the model or alter its coordinates.
        """
        if (width is None) != (height is None):
            raise ValueError("width and height must be provided together")
        if width is not None and height is not None:
            validate_dimensions(width, height)
            self.width = width
            self.height = height
        mid = (self.width // 2, self.height // 2)
        self.snake: list[Position] = [mid]
        # `direction` is the *committed* heading — the way the last step actually
        # moved. Pending turns are queued in `_pending_turns` and applied one per
        # step so that rapid keys can never compound into a reversal.
        self.direction = Direction.RIGHT
        self._pending_turns: list[Direction] = []
        self.symbols_consumed = 0
        self.current_world = 0
        self.symbols_in_current_world = 0
        # Honour the floor even at the start, so a fast `--speed` can't begin
        # the game already past the safe tick rate (see `min_speed_interval`).
        self.current_interval = max(
            self.config.min_speed_interval, self.config.initial_speed_interval
        )
        self.game_over = False
        self.won = False
        self.paused = False
        self.place_food()

    def place_food(self) -> None:
        """Place food uniformly on an empty cell with bounded work.

        Draw one rank among the free cells, then map it to a row-major board
        index by skipping occupied indices. Work is bounded by the snake length,
        rather than board area or the luck of repeated coordinate sampling.
        """
        occupied = {y * self.width + x for x, y in self.snake}
        free_cell_count = self.width * self.height - len(occupied)
        # `step()` declares a win before requesting food on a valid full board.
        # Keep this defensive no-op so a direct/mistaken call can never hang.
        if free_cell_count <= 0:
            return

        position_index = self.rng.randrange(free_cell_count)
        for occupied_index in sorted(occupied):
            if occupied_index > position_index:
                break
            position_index += 1

        self.food = (position_index % self.width, position_index // self.width)
        self.food_symbol = self.world_path.get_food_character(self.current_world)

    def turn(self, new_direction: Direction) -> None:
        """Queue a direction change to be applied on an upcoming step.

        Turns are buffered rather than applied immediately: several keys pressed
        within a single tick must not compound into a 180° reversal. Snake heading
        RIGHT, then UP then LEFT pressed in quick succession would each be a legal
        turn relative to the previous *input* (RIGHT→UP, UP→LEFT) yet leave the
        snake about to step LEFT into its own neck.

        Each turn is validated against the heading it will actually follow — the
        last already-queued turn, or the committed `direction` if the queue is
        empty — so the snake can never reverse onto itself no matter how fast the
        keys arrive. Redundant or reversing turns are dropped, as is anything past
        `config.max_buffered_turns` (kept small so the snake doesn't keep turning
        long after the player stops pressing keys).
        """
        reference = self._pending_turns[-1] if self._pending_turns else self.direction
        if new_direction == reference:
            return
        if not GameRules.is_valid_turn(reference, new_direction):
            return
        if len(self._pending_turns) >= self.config.max_buffered_turns:
            return
        self._pending_turns.append(new_direction)

    def step(self) -> StepResult:
        """Advance the game by one step and report what happened.

        Owns every consequence of a tick — movement, world transition, speed-up,
        and game-over — returning a `StepResult` for the view to react to instead
        of leaving it to infer them from changes in snake length or world index.
        """
        if self.game_over or self.paused:
            return StepResult()
        # Commit at most one buffered turn per step; this is what guarantees a
        # single tick can never reverse the snake (see `turn`).
        if self._pending_turns:
            self.direction = self._pending_turns.pop(0)
        new_head_pos = GameRules.calculate_new_position(
            self.snake[0], self.direction, self.width, self.height
        )
        grows = GameRules.is_food_collision(new_head_pos, self.food)
        # Only include the tail in collision check if we grow this turn
        body_to_check = self.snake if grows else self.snake[:-1]
        if GameRules.is_self_collision(new_head_pos, body_to_check):
            self.game_over = True
            return StepResult(game_over=True)

        self.snake.insert(0, new_head_pos)
        if not grows:
            self.snake.pop()
            return StepResult(moved=True)

        self.symbols_consumed += 1
        self.symbols_in_current_world += 1
        previous_world = self.current_world
        self.check_world_transition()
        world_changed = self.current_world != previous_world
        # Clamp to the floor: the geometric speed-up is otherwise unbounded and
        # would eventually outrun the event loop and crash the app (see
        # `config.min_speed_interval`).
        self.current_interval = max(
            self.config.min_speed_interval,
            self.current_interval * self.config.speed_increase_factor,
        )
        # A board with no empty cell left is a win: the snake covers every cell.
        # End here, before `place_food()` (which has no empty cell to find and
        # would otherwise spin), so a board-solving player terminates cleanly.
        if len(self.snake) == self.width * self.height:
            self.game_over = True
            self.won = True
            return StepResult(
                moved=True,
                ate_food=True,
                world_changed=world_changed,
                new_world=self.current_world if world_changed else None,
                game_over=True,
                won=True,
            )
        self.place_food()
        return StepResult(
            moved=True,
            ate_food=True,
            world_changed=world_changed,
            new_world=self.current_world if world_changed else None,
        )

    def check_world_transition(self) -> None:
        """Check if player should move to next world."""
        if self.symbols_in_current_world >= self.config.symbols_per_world:
            self.current_world += 1
            self.symbols_in_current_world = 0

    def get_moves_per_second(self) -> float:
        """Get current speed as moves per second."""
        return 1.0 / self.current_interval

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

    def set_food_position(self, position: Position, symbol: str = None) -> None:
        """Set food position for testing."""
        if not self._is_valid_position(position):
            raise ValueError(f"Food position {position} is out of bounds")
        self.food = position
        self.food_symbol = symbol or self.world_path.get_food_character(
            self.current_world
        )
