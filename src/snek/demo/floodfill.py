"""Organic hunter — per-tick tail-aware flood-fill, biased to food (the default).

Stateless per tick. Enumerate the (at most 3) legal non-reversing turns, simulate
one step for each (correctly modelling tail-vacate vs grow-on-food), and score the
resulting position. The score is dominated by reachable free-space via a
tail-aware flood-fill (the tail recedes as the fill spends ticks), with toroidal
distance-to-food only breaking ties among moves that are "roomy enough". Lively
and varied (it occasionally traps itself, ~22% mortal on 20x10), which makes the
liveliest attract-loop demo — hence the active default.

Contract compliance: every neighbour goes through the shared toroidal helper
(resize-safe, no cached state); the obstacle set models the vacating tail; only
non-reversing turns are considered and exactly one `Direction` is returned; when
every legal move is immediately fatal it still returns a legal move (dies
deterministically) rather than `None`.
"""

from collections import deque

from ..game_rules import Direction, Position
from ._helpers import blocked_cells, legal_turns, neighbour, toroidal_manhattan
from .base import DemoStrategy


class FloodFillStrategy(DemoStrategy):
    """Per-step space-maximising survival move, biased toward food."""

    def get_next_direction(self) -> Direction | None:
        g = self.game
        head = g.snake[0]
        body = g.snake  # list, head..tail

        legal = legal_turns(g)

        # (safe_roomy, area, food_dist, direction)
        scored: list[tuple[bool, int, int, Direction]] = []
        for d in legal:
            nxt = neighbour(g, head, d)
            grows = nxt == g.food
            future_solid = blocked_cells(g, grows)
            new_body = [nxt] + (body if grows else body[:-1])

            # Immediate-fatal check mirrors Game.step's collision rule exactly.
            if nxt in future_solid:
                continue

            area = self._reachable_area(nxt, new_body)
            snake_len = len(new_body)
            safe_roomy = area >= snake_len
            fdist = toroidal_manhattan(g, nxt, g.food)
            scored.append((safe_roomy, area, fdist, d))

        if not scored:
            # Every legal move is immediately fatal: no escape exists. Return a
            # legal move anyway (deterministic) rather than None, so a turn is
            # still issued and the snake never coasts straight uncommanded.
            return legal[0] if legal else None

        roomy = [s for s in scored if s[0]]
        if roomy:
            # Trend toward food; tie-break on MORE area (keep options open).
            best = min(roomy, key=lambda s: (s[2], -s[1]))
        else:
            # No roomy move: pure survival -> most space, then nearer food.
            best = max(scored, key=lambda s: (s[1], -s[2]))
        return best[3]

    def _reachable_area(self, start: Position, new_body: list[Position]) -> int:
        """Tail-aware flood-fill: count free cells reachable from ``start``.

        ``new_body`` is the snake AFTER the candidate move (head first, tail last),
        so ``start == new_body[0]``. Body cells are obstacles, but the tail recedes
        as we move: a cell occupied by ``new_body[i]`` becomes free after
        ``len(new_body) - i`` more ticks (the tail, the last index, frees first). A
        body cell is enterable at BFS depth ``dist`` iff
        ``dist >= ticks_until_free``. The fill is capped at ``len(new_body) + 1``
        cells -- enough to decide ``safe_roomy`` and bound the cost.
        """
        g = self.game
        body_index = {pos: i for i, pos in enumerate(new_body)}
        length = len(new_body)
        cap = length + 1
        seen = {start}
        q = deque([(start, 0)])
        count = 0
        while q and count < cap:
            cell, depth = q.popleft()
            count += 1
            for d in Direction:
                nb = neighbour(g, cell, d)
                if nb in seen:
                    continue
                idx = body_index.get(nb)
                if idx is not None:
                    ticks_until_free = length - idx  # tail (last idx) frees soonest
                    if depth + 1 < ticks_until_free:
                        # Still solid by the time the fill would arrive.
                        continue
                seen.add(nb)
                q.append((nb, depth + 1))
        return count
