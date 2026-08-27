"""Naive tier — beeline to the food, no survival planning.

Picks, among the legal non-reversing moves that don't collide, the one minimising
toroidal Manhattan distance to the food. Deliberately dumb: no flood-fill, no
lookahead, no reachability check — it just chases the food and traps itself, dying
young (~31 foods on 20x10). Its naivety is purely the absence of *planning*, not a
misread of the board: like every strategy it models the rules correctly — only
non-reversing moves, and the tail counts as vacated on a non-growing step
(contract #2) — so it never throws away a legal escape; it simply doesn't look far
enough ahead to keep one. Still honours contract #1 (when every move collides it
dies forward on a legal direction rather than returning `None`).
"""

from typing_extensions import override

from ..game_rules import Direction
from ._helpers import blocked_cells, legal_turns, neighbour, toroidal_manhattan
from .base import DemoStrategy


class GreedyStrategy(DemoStrategy):
    """Greedy distance-minimiser with no lookahead (the weak anchor)."""

    @override
    def get_next_direction(self) -> Direction | None:
        g = self.game
        head = g.snake[0]
        legal = legal_turns(g)

        best: Direction | None = None
        best_dist: int | None = None
        for d in legal:
            nxt = neighbour(g, head, d)
            # Tail-vacate aware (contract #2): the tail's cell is enterable on a
            # non-growing step (the engine checks against snake[:-1]).
            if nxt in blocked_cells(g, nxt == g.food):
                continue
            dist = toroidal_manhattan(g, nxt, g.food)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best = d
        if best is not None:
            return best
        # Contract #1: every non-reversing move collides — emit a legal move and
        # die forward rather than returning None and coasting straight uncommanded.
        return legal[0] if legal else None
