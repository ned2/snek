"""Tests for the pluggable demo-mode AI strategies (`snek.demo`).

Covers the shared correctness contract (which bakes in the enduring 0005 bugs
B1/B4/B7), the Hamiltonian cycle structure + end-to-end board solve, and a fast
skill-floor smoke. The benchmark harness is the *quantitative* gate; these tests
are the behavioural guardrails that run in CI.
"""

import random
from dataclasses import replace

import pytest

from snek.config import default_config
from snek.demo import (
    DEFAULT_STRATEGY,
    STRATEGIES,
    DemoStrategy,
    FloodFillStrategy,
    GreedyStrategy,
    HamiltonianStrategy,
    SafeBfsStrategy,
    make_demo_ai,
)
from snek.game import Game
from snek.game_rules import Direction, GameRules

# Every strategy is tail-vacate aware (contract #2): none steps into a cell the
# tail will vacate when a survivable move exists. `greedy` is naive only in that it
# never *plans* — it still models the board correctly.
TAIL_VACATE = list(STRATEGIES)
# Strategies that re-evaluate every move from scratch each tick, so they escape
# even contrived states. `hamiltonian` relies on a cycle invariant it maintains
# from a length-1 start, so it is not robust to artificially-constructed snakes.
PER_TICK_SURVIVAL = ["greedy", "safe-bfs", "floodfill"]
WALLED = replace(default_config, walls=True)
WRAPPING = replace(default_config, walls=False)


def _game(w: int, h: int, seed: int, walls: bool = False) -> Game:
    config = WALLED if walls else WRAPPING
    return Game(width=w, height=h, config=config, rng=random.Random(seed))


def _legal(game: Game) -> list[Direction]:
    return [d for d in Direction if GameRules.is_valid_turn(game.direction, d)]


def _survivable(game: Game, direction: Direction) -> bool:
    """True if stepping `direction` lands on a cell that won't be occupied.

    Models the vacating tail exactly like `Game.step` (collision is checked
    against `snake[:-1]` unless the move eats).
    """
    head = game.snake[0]
    nxt = GameRules.next_position(
        head, direction, game.width, game.height, game.config.walls
    )
    if nxt is None:  # a wall
        return False
    grows = nxt == game.food
    blocked = set(game.snake) if grows else set(game.snake[:-1])
    return nxt not in blocked


def _adjacent(
    a: tuple[int, int], b: tuple[int, int], w: int, h: int, walls: bool
) -> bool:
    return any(GameRules.next_position(a, d, w, h, walls) == b for d in Direction)


def _is_valid_cycle(
    cells: list[tuple[int, int]], w: int, h: int, walls: bool = False
) -> bool:
    """Every cell visited exactly once, consecutive pairs (incl. last->first)
    adjacent — across the wrap seam only when the board has no walls."""
    n = len(cells)
    if n != w * h or len(set(cells)) != w * h:
        return False
    return all(_adjacent(cells[i], cells[(i + 1) % n], w, h, walls) for i in range(n))


def _play(name: str, w: int, h: int, seed: int, cap: int, walls: bool = False) -> Game:
    """Drive a headless game to completion (or the step cap) and return it."""
    game = _game(w, h, seed, walls)
    ai = STRATEGIES[name](game)
    steps = 0
    while not game.game_over and steps < cap:
        direction = ai.get_next_direction()
        if direction:
            game.turn(direction)
        game.step()
        steps += 1
    return game


# --------------------------------------------------------------------------- registry


def test_registry_and_factory():
    """The registry holds the four strategies; the factory builds the default."""
    assert set(STRATEGIES) == {"greedy", "safe-bfs", "floodfill", "hamiltonian"}
    assert DEFAULT_STRATEGY == "floodfill"
    assert DEFAULT_STRATEGY in STRATEGIES
    for cls in STRATEGIES.values():
        assert issubclass(cls, DemoStrategy)

    game = Game(width=20, height=10, config=WRAPPING, rng=random.Random(0))
    assert isinstance(make_demo_ai(game), FloodFillStrategy)  # default
    assert isinstance(make_demo_ai(game, "floodfill"), FloodFillStrategy)
    assert isinstance(make_demo_ai(game, "greedy"), GreedyStrategy)
    assert isinstance(make_demo_ai(game, "safe-bfs"), SafeBfsStrategy)
    assert isinstance(make_demo_ai(game, "hamiltonian"), HamiltonianStrategy)


# ----------------------------------------------------------------- contract: B1 + #4


@pytest.mark.parametrize("walls", [False, True], ids=["wrap", "walls"])
@pytest.mark.parametrize("name", list(STRATEGIES))
def test_never_silent_none(name, walls):
    """Contract #1 (0005-B1): never return None while a legal move exists; never
    return a reversing turn."""
    for seed in range(6):
        game = _game(20, 10, seed, walls)
        ai = STRATEGIES[name](game)
        steps = 0
        while not game.game_over and steps < 500:
            legal = _legal(game)
            direction = ai.get_next_direction()
            if legal:
                assert direction is not None, (
                    f"{name} seed={seed} step={steps}: returned None with legal {legal}"
                )
                assert direction in legal, (
                    f"{name} seed={seed} step={steps}: {direction} reverses heading "
                    f"{game.direction}"
                )
            else:
                assert direction is None
            if direction:
                game.turn(direction)
            game.step()
            steps += 1


@pytest.mark.parametrize("name", list(STRATEGIES))
def test_deterministic(name):
    """Contract #4: a pure function of game state — identical seed, identical
    move sequence (no RNG, no set-iteration-order dependence)."""

    def run() -> list[Direction | None]:
        game = Game(width=16, height=10, config=WRAPPING, rng=random.Random(123))
        ai = STRATEGIES[name](game)
        seq: list[Direction | None] = []
        steps = 0
        while not game.game_over and steps < 300:
            direction = ai.get_next_direction()
            seq.append(direction)
            if direction:
                game.turn(direction)
            game.step()
            steps += 1
        return seq

    assert run() == run()


# ----------------------------------------------------------------- contract: B4


@pytest.mark.parametrize("walls", [False, True], ids=["wrap", "walls"])
@pytest.mark.parametrize("name", TAIL_VACATE)
def test_takes_survivable_move_when_one_exists(name, walls):
    """Contract #2 (0005-B4): model the vacating tail; whenever a survivable
    legal move exists, take one rather than stepping into a still-occupied cell
    or, with walls, off the board.

    Holds for *every* strategy, including `greedy` — being naive means not
    planning ahead, not misreading which cells are legal."""
    for seed in range(6):
        game = _game(20, 10, seed, walls)
        ai = STRATEGIES[name](game)
        steps = 0
        while not game.game_over and steps < 500:
            survivable = [d for d in _legal(game) if _survivable(game, d)]
            direction = ai.get_next_direction()
            if survivable:
                assert direction in survivable, (
                    f"{name} seed={seed} step={steps}: chose {direction}, "
                    f"survivable={survivable}"
                )
            if direction:
                game.turn(direction)
            game.step()
            steps += 1


@pytest.mark.parametrize("name", PER_TICK_SURVIVAL)
def test_b4_vacating_tail_escape(name):
    """The exact 0005-B4 scenario: boxed in except for the cell the tail vacates.

    snake [(2,2),(2,1),(2,3),(3,2)] heading RIGHT — UP/DOWN hit the body, LEFT is
    a reversal, and RIGHT enters the *current tail cell*, which is enterable
    because the tail recedes on this non-growing step. A tail-vacate-aware
    strategy must escape via RIGHT instead of dying.
    """
    game = Game(width=10, height=10, config=WRAPPING, rng=random.Random(0))
    game.set_snake_position([(2, 2), (2, 1), (2, 3), (3, 2)])
    game.direction = Direction.RIGHT
    game.set_food_position((8, 8))  # well out of the way

    direction = STRATEGIES[name](game).get_next_direction()
    assert direction == Direction.RIGHT  # the unique survivable non-reversing move

    game.turn(direction)
    game.step()
    assert not game.game_over


# ------------------------------------------------- hamiltonian structure (B7 incl.)


@pytest.mark.parametrize("w,h", [(20, 10), (6, 4), (10, 8), (5, 4), (4, 5)])
def test_hamiltonian_builds_valid_cycle(w, h):
    """An even-sided board admits a true Hamiltonian cycle on the torus."""
    game = Game(width=w, height=h, config=WRAPPING, rng=random.Random(0))
    ai = HamiltonianStrategy(game)
    ai.get_next_direction()  # triggers the build
    assert ai._built_for == (w, h, False)
    assert ai._is_true_cycle is True
    assert _is_valid_cycle(ai.cycle, w, h)


@pytest.mark.parametrize("w,h", [(20, 10), (6, 4), (5, 4), (4, 5), (7, 6), (6, 7)])
def test_hamiltonian_builds_a_cycle_without_wrap_edges_on_walled_boards(w, h):
    """A walled board has a Hamiltonian cycle iff it has an even cell count. The
    torus weave crosses an edge when the other side is odd, so those boards need
    the construction that stays on the board."""
    game = _game(w, h, 0, walls=True)
    ai = HamiltonianStrategy(game)
    ai.get_next_direction()
    assert ai._built_for == (w, h, True)
    assert ai._is_true_cycle is True
    assert _is_valid_cycle(ai.cycle, w, h, walls=True)


def test_hamiltonian_odd_odd_walled_board_degrades_to_path():
    game = _game(5, 5, 0, walls=True)
    ai = HamiltonianStrategy(game)
    direction = ai.get_next_direction()
    assert ai._is_true_cycle is False
    assert len(set(ai.cycle)) == 25
    assert direction is None or GameRules.is_valid_turn(game.direction, direction)


@pytest.mark.parametrize("w,h", [(5, 5), (7, 3)])
def test_hamiltonian_odd_odd_degrades_to_path(w, h):
    """Odd x odd admits no cycle; degrade to a covering path without error."""
    game = Game(width=w, height=h, config=WRAPPING, rng=random.Random(0))
    ai = HamiltonianStrategy(game)
    direction = ai.get_next_direction()  # must not raise
    assert ai._built_for == (w, h, False)
    assert ai._is_true_cycle is False
    # Still covers every cell exactly once (a Hamiltonian path).
    assert len(ai.cycle) == w * h and len(set(ai.cycle)) == w * h
    assert direction is None or GameRules.is_valid_turn(game.direction, direction)


@pytest.mark.parametrize("w,h", [(5, 5), (7, 3), (5, 7), (9, 9)])
def test_hamiltonian_survives_odd_boards(w, h):
    """Odd x odd boards have no Hamiltonian cycle, so the strategy follows a
    *path* with shortcuts disabled and its tail-vacate-aware fallback bridging the
    seam. It must still honour contract #2 over a FULL game — never stepping into
    its own body when a survivable move exists, and never dying a self-collision
    death. (Regression: the cycle-successor used to be emitted unchecked in path
    mode, walking the snake into itself; the seam fallback's `snake[:-1]` rule is
    also exercised heavily here.)
    """
    cap = 3000
    for seed in range(5):
        game = Game(width=w, height=h, config=WRAPPING, rng=random.Random(seed))
        ai = HamiltonianStrategy(game)
        steps = 0
        while not game.game_over and steps < cap:
            survivable = [d for d in _legal(game) if _survivable(game, d)]
            direction = ai.get_next_direction()
            if survivable:
                assert direction in survivable, (
                    f"{w}x{h} seed={seed} step={steps}: chose {direction}, "
                    f"survivable={survivable}"
                )
            if direction:
                game.turn(direction)
            game.step()
            steps += 1
        assert not (game.game_over and not game.won), (
            f"{w}x{h} seed={seed}: self-collision death "
            f"(foods={game.symbols_consumed}, step={steps})"
        )


def test_hamiltonian_fallback_uses_vacating_tail():
    """The Hamiltonian safe-fallback models the vacating tail (contract #2 / B4).

    Heading RIGHT with the tail directly above the head: UP enters the cell the
    tail just vacated (survivable on this non-growing step), while DOWN and RIGHT
    step into the body and LEFT reverses — so UP is the *only* survivable move and
    differs from the enum-order `any_legal` last resort (RIGHT). A `set(snake)`
    regression that ignored the vacating tail would pick RIGHT (into the body), so
    this directly guards the fallback's `snake[:-1]` rule.
    """
    game = Game(width=10, height=10, config=WRAPPING, rng=random.Random(0))
    game.set_snake_position([(5, 5), (5, 6), (6, 5), (5, 4)])  # head (5,5), tail (5,4)
    game.direction = Direction.RIGHT
    game.set_food_position((0, 0))
    assert HamiltonianStrategy(game)._safe_fallback() == Direction.UP


def test_hamiltonian_rebuilds_if_a_fresh_game_uses_a_new_grid():
    """A strategy reused across explicit fresh-grid setup drops stale topology."""
    game = Game(width=20, height=10, config=WRAPPING, rng=random.Random(0))
    ai = HamiltonianStrategy(game)
    ai.get_next_direction()
    assert ai._built_for == (20, 10, False)
    assert len(ai.cycle) == 200

    game.reset(width=12, height=8)
    ai.get_next_direction()
    assert ai._built_for == (12, 8, False)
    assert len(ai.cycle) == 96
    assert _is_valid_cycle(ai.cycle, 12, 8)


@pytest.mark.parametrize(
    "w,h,walls", [(6, 4, False), (8, 6, False), (6, 4, True), (7, 6, True)]
)
def test_hamiltonian_solves_small_board(w, h, walls):
    """End-to-end: the solver fills an even board to a clean win."""
    cells = w * h
    game = _play("hamiltonian", w, h, seed=3, cap=20_000, walls=walls)
    assert game.won, (
        f"hamiltonian did not solve {w}x{h} (foods={game.symbols_consumed})"
    )
    assert game.game_over
    assert len(game.snake) == cells
    # Every cell but the ones the snake grew in to came from food.
    assert game.symbols_consumed == cells - game.config.start_length


# ----------------------------------------------------------------- skill floor


def test_skill_floor_strong_beats_greedy():
    """Fast smoke: every survival strategy clearly outscores naive greedy on a
    small board, and hamiltonian solves every seed."""
    w, h, cap = 8, 6, 500
    seeds = [0, 1, 2]
    results = {
        name: [_play(name, w, h, seed, cap) for seed in seeds] for name in STRATEGIES
    }
    mean_foods = {
        name: sum(game.symbols_consumed for game in games) / len(games)
        for name, games in results.items()
    }

    greedy = mean_foods["greedy"]
    for name in ("safe-bfs", "floodfill", "hamiltonian"):  # the planning strategies
        assert mean_foods[name] > greedy, (
            f"{name} mean {mean_foods[name]} !> greedy mean {greedy}"
        )
    assert all(game.won for game in results["hamiltonian"])


@pytest.mark.parametrize("name", sorted(STRATEGIES))
def test_no_strategy_enters_a_tail_that_is_growing_in(name):
    """While the snake grows in its tail stays put, so its cell is fatal.

    The snake has curled round so its tail is beside its head, with the food
    just beyond it: a strategy that assumed the tail vacates would take it.
    """
    game = Game(width=20, height=11, config=WRAPPING, rng=random.Random(0))
    game.set_food_position((0, 0))
    for turn in (Direction.DOWN, Direction.LEFT, Direction.UP):
        game.turn(turn)
        game.step()
    assert game.snake == [(9, 5), (9, 6), (10, 6), (10, 5)]
    assert game.pending_growth > 0
    game.set_food_position((11, 5))
    direction = STRATEGIES[name](game).get_next_direction()
    assert direction is not None
    game.turn(direction)
    assert not game.step().game_over
