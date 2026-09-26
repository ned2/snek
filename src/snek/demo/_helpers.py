"""Shared, model-correct helpers for demo strategies.

Every strategy routes its board math through here so the four contract
properties (legality, tail-vacate, grid-awareness, determinism) are honoured
uniformly: movement goes through `GameRules` so wrap-around (or, with
`config.walls`, the solid edge) matches the engine exactly, and `blocked_cells`
models the receding tail per `Game.step`'s `snake[:-1]` collision rule. The tail
stays put while the snake grows in to its starting length (`Game.pending_growth`),
as it does on a step that eats.
"""

from ..game import Game
from ..game_rules import Direction, GameRules, Position


def legal_turns(game: Game) -> list[Direction]:
    """The non-reversing turns from the committed heading, in `Direction` order."""
    return [d for d in Direction if GameRules.is_valid_turn(game.direction, d)]


def neighbour(game: Game, pos: Position, direction: Direction) -> Position | None:
    """The cell reached by stepping `direction` from `pos`.

    The board wraps around, unless `config.walls` is set: then a step off the
    board returns None, which callers treat as blocked (moving there is fatal).
    """
    return GameRules.next_position(
        pos, direction, game.width, game.height, game.config.walls
    )


def tail_moves(game: Game, grows: bool) -> bool:
    """Whether the tail leaves its cell this step: not if eating or growing in."""
    return not grows and not game.tail_stays


def blocked_cells(game: Game, grows: bool) -> set[Position]:
    """The cells that block the head this step.

    When the tail moves (the engine checks collision against `snake[:-1]`) its
    current cell is enterable; when eating or growing in the whole body stays put.
    """
    return set(game.snake[:-1]) if tail_moves(game, grows) else set(game.snake)


def body_after(game: Game, head: Position, grows: bool) -> list[Position]:
    """The snake after its head steps to `head` this step, head first."""
    body = game.snake[:-1] if tail_moves(game, grows) else game.snake
    return [head, *body]


def growth_after(game: Game, grows: bool) -> int:
    """The growing in left after this step: a step that doesn't eat uses one."""
    return game.pending_growth if grows else max(0, game.pending_growth - 1)


def board_distance(game: Game, a: Position, b: Position) -> int:
    """Manhattan distance between two cells, the short way round if it wraps."""
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    if game.config.walls:
        return dx + dy
    return min(dx, game.width - dx) + min(dy, game.height - dy)
