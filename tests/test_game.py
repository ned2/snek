"""Unit tests for the Game class."""

from dataclasses import replace
import random

import pytest

from snek.config import GameConfig
from snek.game import Game, StepResult
from snek.game_rules import Direction


class _FixedRankRng:
    """Minimal position RNG that records and returns one requested free rank."""

    def __init__(self, rank: int) -> None:
        self.rank = rank
        self.calls: list[int] = []

    def randrange(self, stop: int) -> int:
        self.calls.append(stop)
        if not 0 <= self.rank < stop:
            raise AssertionError(f"rank {self.rank} outside range(0, {stop})")
        return self.rank


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

    def test_replacing_one_default_config_is_isolated(self) -> None:
        """Games may share the immutable default without sharing later overrides."""
        first = Game()
        second = Game()
        shared_default = second.config
        original_scale = shared_default.cell_scale

        assert first.config is shared_default
        first.config = replace(first.config, cell_scale=original_scale + 1)

        assert first.config.cell_scale == original_scale + 1
        assert second.config is shared_default
        assert second.config.cell_scale == original_scale

    def test_explicit_config_is_retained_as_a_shareable_value(self) -> None:
        """Callers may intentionally reuse one immutable config value."""
        config = GameConfig(cell_scale=2)

        first = Game(config=config)
        second = Game(config=config)

        assert first.config is config
        assert second.config is config

    def test_custom_dimensions(self):
        """Test game with custom dimensions."""
        game = Game(width=30, height=20)
        assert game.width == 30
        assert game.height == 20
        assert game.snake[0] == (15, 10)  # Center position

    def test_none_dimensions_fall_back_independently(self):
        """Only `None` selects a default; an explicit peer dimension is retained."""
        game = Game(width=None, height=12)
        assert (game.width, game.height) == (game.config.default_grid_width, 12)

    @pytest.mark.parametrize("value", [0, -1, 2.5, "10", True])
    @pytest.mark.parametrize("field", ["width", "height"])
    def test_invalid_dimensions_are_rejected(self, field: str, value: object) -> None:
        """Invalid values fail at construction, not in random food placement."""
        dimensions = {"width": 10, "height": 10, field: value}
        with pytest.raises(ValueError, match=field):
            Game(**dimensions)

    def test_one_by_one_board_is_rejected_before_construction(self):
        with pytest.raises(ValueError, match="board must contain at least 2 cells"):
            Game(width=1, height=1)

    def test_minimum_one_by_two_board_has_defined_win_semantics(self):
        """The smallest supported board initializes fully and wins coherently."""
        game = Game(width=1, height=2, rng=random.Random(0))
        assert game.snake == [(0, 1)]
        assert game.food == (0, 0)
        assert isinstance(game.food_symbol, str)

        game.turn(Direction.UP)
        result = game.step()

        assert result.won is True
        assert game.won is True
        assert game.game_over is True
        assert len(game.snake) == 2

    def test_very_large_sparse_board_is_supported(self):
        """Dimensions are not subject to an arbitrary UI-sized upper bound."""
        game = Game(width=10**12, height=2, rng=random.Random(0))
        assert game.width == 10**12
        assert 0 <= game.food[0] < game.width
        assert 0 <= game.food[1] < game.height

    def test_every_constructed_game_has_food_attributes(self):
        """Supported dimensions always initialize the complete step contract."""
        game = Game(width=1, height=2)
        assert hasattr(game, "food")
        assert hasattr(game, "food_symbol")

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

    @pytest.mark.parametrize(
        ("rank", "expected"),
        [(0, (1, 0)), (1, (0, 1)), (2, (1, 1)), (3, (3, 1))],
    )
    def test_free_rank_maps_past_occupied_cells(
        self, rank: int, expected: tuple[int, int]
    ) -> None:
        """A sampled free rank maps deterministically in row-major order."""
        game = Game(width=4, height=2, rng=random.Random(0))
        game.set_snake_position([(0, 0), (2, 0), (3, 0), (2, 1)])
        rank_rng = _FixedRankRng(rank)
        game.rng = rank_rng

        game.place_food()

        assert game.food == expected
        assert rank_rng.calls == [4]

    def test_large_nearly_full_board_uses_one_position_draw(self) -> None:
        """Structural performance guard: no retry loop or whole-board scan.

        A call-count budget is deterministic where a wall-clock assertion would
        be flaky. The only free cell is the last of a 200x50 board.
        """
        width, height = 200, 50
        free = (width - 1, height - 1)
        game = Game(width=width, height=height, rng=random.Random(0))
        game.set_snake_position(
            [(x, y) for y in range(height) for x in range(width) if (x, y) != free]
        )
        rank_rng = _FixedRankRng(0)
        game.rng = rank_rng

        game.place_food()

        assert game.food == free
        assert rank_rng.calls == [1]

    def test_repeated_placement_is_in_bounds_and_off_snake(self) -> None:
        game = Game(width=17, height=11, rng=random.Random(1234))
        game.set_snake_position([(x, 5) for x in range(14)])

        for _ in range(500):
            game.place_food()
            assert 0 <= game.food[0] < game.width
            assert 0 <= game.food[1] < game.height
            assert game.food not in game.snake


class TestDeterminism:
    """Seeded position+symbol streams are reproducible for equal state histories.

    Exact coordinates are not a compatibility promise: bounded free-rank food
    placement intentionally changed the legacy rejection-sampling sequence.
    """

    def _food_sequence(
        self, seed: int, steps: int
    ) -> list[tuple[tuple[int, int], str]]:
        """Collect the (food_position, food_symbol) pairs a seeded game produces.

        Walks through every world so each world's shuffled character pool is exercised,
        not just world 0's.
        """
        game = Game(width=10, height=10, rng=random.Random(seed))
        sequence = [(game.food, game.food_symbol)]
        for index in range(steps):
            game.current_world = index % len(game.world_path.worlds)
            game.place_food()
            sequence.append((game.food, game.food_symbol))
        return sequence

    def test_same_seed_reproduces_position_and_symbol(self):
        """Two same-seed games produce identical food position+symbol streams.

        Guards the rng threading through WorldPath: before WorldPath shared the game's
        rng, food *symbol* selection used the module-level random and diverged even for a
        fixed seed.
        """
        first = self._food_sequence(1234, 40)
        second = self._food_sequence(1234, 40)
        assert first == second
        # The equality is only meaningful if symbols actually vary across placements.
        assert len({symbol for _, symbol in first}) > 1

    def test_different_seeds_diverge(self):
        """Distinct seeds produce distinct streams, so the rng is genuinely consulted."""
        assert self._food_sequence(1, 40) != self._food_sequence(2, 40)


class TestMovement:
    """Test snake movement mechanics."""

    def test_turn_valid(self):
        """A valid turn is buffered and applied on the next step."""
        game = Game()
        game.direction = Direction.RIGHT

        game.turn(Direction.UP)
        # The committed heading only changes once the step consumes the turn.
        assert game.direction == Direction.RIGHT
        game.step()
        assert game.direction == Direction.UP

    def test_turn_invalid(self):
        """A reversing turn is ignored; a perpendicular one is accepted."""
        game = Game()
        game.direction = Direction.RIGHT

        # Can't turn to the opposite direction...
        game.turn(Direction.LEFT)
        game.step()
        assert game.direction == Direction.RIGHT

        # ...but can turn perpendicular.
        game.turn(Direction.UP)
        game.step()
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


class TestTurnBuffering:
    """Rapid key presses must never reverse the snake onto its own neck."""

    def _rightward_snake(self) -> Game:
        """A length-3 snake heading RIGHT with its body trailing to the left."""
        game = Game(width=20, height=10)
        game.set_snake_position([(10, 5), (9, 5), (8, 5)])
        game.direction = Direction.RIGHT
        game.set_food_position((0, 0))  # keep food well out of the way
        return game

    def test_perpendicular_then_reverse_does_not_kill(self):
        """UP then LEFT in one tick (heading RIGHT) must not be a 180° reversal.

        This is the reported bug: each turn is legal relative to the previous
        *input*, but applied together they step the head back into the neck.
        """
        game = self._rightward_snake()

        game.turn(Direction.UP)
        game.turn(Direction.LEFT)
        result = game.step()

        # First buffered turn wins this tick; the snake goes UP, not back LEFT.
        assert game.direction == Direction.UP
        assert game.game_over is False
        assert result.game_over is False
        assert game.snake[0] == (10, 4)

    def test_buffered_turns_apply_one_per_step(self):
        """A fast L-turn is honoured: UP this step, the queued LEFT the next."""
        game = self._rightward_snake()

        game.turn(Direction.UP)
        game.turn(Direction.LEFT)

        game.step()
        assert game.direction == Direction.UP

        game.step()
        assert game.direction == Direction.LEFT
        assert game.game_over is False

    def test_direct_reversal_is_dropped(self):
        """A single key opposite the heading is ignored outright."""
        game = self._rightward_snake()

        game.turn(Direction.LEFT)  # straight reversal of RIGHT
        game.step()

        assert game.direction == Direction.RIGHT
        assert game.game_over is False

    def test_buffer_is_bounded(self):
        """No more than `max_buffered_turns` turns are ever queued."""
        game = self._rightward_snake()

        # A rotating sequence where each turn is legal relative to the last.
        game.turn(Direction.UP)
        game.turn(Direction.LEFT)
        game.turn(Direction.DOWN)  # would be a valid 3rd turn, but the buffer is full

        assert len(game._pending_turns) == game.config.max_buffered_turns

    def test_redundant_turn_is_not_queued(self):
        """Pressing the current heading again does nothing."""
        game = self._rightward_snake()

        game.turn(Direction.RIGHT)

        assert game._pending_turns == []


class TestStepResult:
    """Test the StepResult contract that Game.step() returns to the view."""

    def _game_with_food_ahead(self) -> Game:
        """A roomy game with food directly in front of the right-moving head."""
        game = Game(width=40, height=40, rng=random.Random(0))
        head = game.snake[0]
        game.food = (head[0] + 1, head[1])
        return game

    def test_noop_when_paused(self):
        """A paused game reports that nothing happened."""
        game = Game()
        game.paused = True
        assert game.step() == StepResult()

    def test_noop_when_game_over(self):
        """A finished game reports that nothing happened."""
        game = Game()
        game.game_over = True
        assert game.step() == StepResult()

    def test_plain_move(self):
        """A move into empty space reports moved only."""
        game = Game(width=40, height=40)
        head = game.snake[0]
        game.food = (head[0], head[1] + 2)  # not where a RIGHT step lands
        assert game.step() == StepResult(moved=True)

    def test_self_collision_reports_game_over(self):
        """Running into the body reports game_over and sets the flag."""
        game = Game()
        game.snake = [(5, 5), (4, 5), (4, 4), (5, 4), (6, 4)]
        game.direction = Direction.UP  # steps back into (5, 4)
        game.food = (0, 0)  # keep food out of the way
        assert game.step() == StepResult(game_over=True)
        assert game.game_over is True

    def test_eat_without_world_change(self):
        """Eating mid-world reports ate_food but not world_changed."""
        game = self._game_with_food_ahead()
        assert game.step() == StepResult(
            moved=True, ate_food=True, world_changed=False, new_world=None
        )

    def test_eat_crossing_world_boundary(self):
        """Eating a world's final food reports world_changed and the new index."""
        game = self._game_with_food_ahead()
        game.symbols_in_current_world = game.config.symbols_per_world - 1

        result = game.step()

        assert result.ate_food is True
        assert result.world_changed is True
        assert result.new_world == 1
        assert game.current_world == 1

    def test_eat_scales_speed(self):
        """Eating speeds the game up by the configured factor (model owns the rule)."""
        game = self._game_with_food_ahead()
        before = game.current_interval

        game.step()

        assert game.current_interval == before * game.config.speed_increase_factor


class TestSpeedFloor:
    """The tick interval is clamped so the speed-up can't outrun the event loop.

    Without a floor the geometric speed-up is unbounded; on a large board the
    demo eats enough food to drive the interval into the tens of microseconds,
    far faster than the event loop can service a step + render, and the app
    crashes mid-game. See `config.min_speed_interval`.
    """

    def _eat_foods(self, game: Game, n: int) -> None:
        """Eat `n` foods by always parking the next food in front of the head.

        The board wraps and the snake grows (tail stays put) each food, so a
        single wide, short board lets us eat far more foods than the geometric
        speed-up needs to reach the floor — without any self-collision.
        """
        for _ in range(n):
            head = game.snake[0]
            game.food = ((head[0] + 1) % game.width, head[1])
            game.step()

    def test_interval_clamps_to_floor_and_no_crash_path(self):
        """Eating well past the floor pins the interval at the floor, game alive."""
        game = Game(width=400, height=3)
        # ~195 foods reaches the 0.002s floor from 0.1s; 300 is comfortably past.
        self._eat_foods(game, 300)
        assert game.game_over is False
        assert game.current_interval == pytest.approx(game.config.min_speed_interval)

    def test_speed_never_exceeds_cap(self):
        """No matter how many foods are eaten, moves/sec stays under the cap."""
        game = Game(width=400, height=3)
        cap = 1.0 / game.config.min_speed_interval
        for _ in range(300):
            head = game.snake[0]
            game.food = ((head[0] + 1) % game.width, head[1])
            game.step()
            assert game.get_moves_per_second() <= cap + 1e-9

    def test_fast_start_above_cap_is_rejected(self):
        """An unsafe requested start speed fails instead of being silently changed."""
        with pytest.raises(ValueError, match="initial_speed_interval"):
            GameConfig(initial_speed_interval=0.00001)


class TestWinState:
    """Filling the board is a win, not an infinite loop in `place_food`."""

    def test_full_board_is_a_win(self):
        """Eating the last food fills the board and ends the game as a win.

        3x2 board: the snake covers all but (2,1); food sits on (2,1); stepping
        DOWN onto it grows the snake to cover every cell.
        """
        game = Game(width=3, height=2, rng=random.Random(0))
        game.snake = [(2, 0), (1, 0), (0, 0), (0, 1), (1, 1)]
        game.direction = Direction.DOWN
        game.set_food_position((2, 1))

        result = game.step()

        assert result.won is True
        assert result.game_over is True
        assert result.ate_food is True
        assert game.won is True
        assert game.game_over is True
        assert len(game.snake) == game.width * game.height

    def test_place_food_on_full_board_does_not_hang(self):
        """The defensive guard makes `place_food` a no-op on a full board.

        Without the guard this would spin forever searching for an empty cell;
        the call must return promptly and leave the (now meaningless) food alone.
        """
        game = Game(width=3, height=2, rng=random.Random(0))
        game.snake = [(x, y) for y in range(2) for x in range(3)]  # every cell
        game.set_food_position((0, 0))
        rank_rng = _FixedRankRng(0)
        game.rng = rank_rng

        game.place_food()  # must return immediately, not hang

        assert game.food == (0, 0)  # untouched — the guard short-circuited
        assert rank_rng.calls == []

    def test_won_defaults_false(self):
        """A fresh game and a plain StepResult are not in a won state."""
        assert Game().won is False
        assert StepResult().won is False
        assert StepResult(moved=True).won is False


class TestPositionSetup:
    """Test fresh-grid and explicit-position setup helpers."""

    def test_reset_can_establish_a_fresh_grid(self):
        """Initial UI layout may choose dimensions before any play state exists."""
        game = Game(width=10, height=10)
        game.symbols_consumed = 10
        game.game_over = True

        game.reset(width=20, height=12)

        assert (game.width, game.height) == (20, 12)
        assert game.snake == [(10, 6)]
        assert game.food not in game.snake
        assert game.symbols_consumed == 0
        assert game.game_over is False

    def test_reset_dimensions_must_be_supplied_together(self):
        """A partial dimension update cannot leave the model half-reconfigured."""
        game = Game(width=10, height=10)

        with pytest.raises(
            ValueError, match="width and height must be provided together"
        ):
            game.reset(width=20)

    @pytest.mark.parametrize(
        ("width", "height"),
        [(0, 10), (10, -1), (1.5, 10), (1, 1)],
    )
    def test_reset_rejects_invalid_dimensions(
        self, width: object, height: object
    ) -> None:
        """Fresh-grid setup uses the same boundary as direct construction."""
        game = Game(width=10, height=10)
        before = (game.width, game.height, list(game.snake), game.food)

        with pytest.raises(ValueError):
            game.reset(width=width, height=height)

        assert (game.width, game.height, game.snake, game.food) == before

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
