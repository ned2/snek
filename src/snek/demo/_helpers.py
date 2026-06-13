"""Shared, model-correct helpers for demo strategies.

Every strategy routes its board math through here so the four contract
properties (legality, tail-vacate, resize-tolerance, determinism) are honoured
uniformly: movement goes through `GameRules` so toroidal wrap matches the engine
exactly, and `blocked_cells` models the receding tail per `Game.step`'s
`snake[:-1]` collision rule.
"""

from ..game import Game
from ..game_rules import Direction, GameRules, Position


def legal_turns(game: Game) -> list[Direction]:
    """The non-reversing turns from the committed heading, in `Direction` order."""
    return [d for d in Direction if GameRules.is_valid_turn(game.direction, d)]


def neighbour(game: Game, pos: Position, direction: Direction) -> Position:
    """The cell reached by stepping `direction` from `pos`, with toroidal wrap."""
    return GameRules.calculate_new_position(pos, direction, game.width, game.height)


def blocked_cells(game: Game, grows: bool) -> set[Position]:
    """The cells that block the head this step.

    On a non-growing step the tail vacates (the engine checks collision against
    `snake[:-1]`), so its current cell is enterable; on a growing step the whole
    body stays put.
    """
    return set(game.snake) if grows else set(game.snake[:-1])


def toroidal_manhattan(game: Game, a: Position, b: Position) -> int:
    """Wrap-aware Manhattan distance between two cells on the torus."""
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return min(dx, game.width - dx) + min(dy, game.height - dy)
