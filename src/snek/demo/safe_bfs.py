"""Cautious survivor — shortest path to food gated by a tail-reachability check.

Stateless each tick (holding no cross-tick topology, so it cannot retain a stale
path if model dimensions are freshly established):

1. BFS the board from head to food over the cells the body will NOT occupy,
   modelling the tail as free (it vacates on a non-growing step).
2. If a food path exists, SIMULATE eating along it and accept the path's first
   step ONLY if, after the simulated eat, the new head can still reach its own
   tail (a reachability survival check).
3. If no safe food path, pick the legal neighbour that MAXIMISES reachable free
   space via flood-fill (this naturally chases the tail and stalls safely until a
   path reopens), tie-broken toward keeping the (future) tail reachable, then
   toward food so it resumes progress instead of looping.
4. If even that is empty, take any legal non-self-colliding neighbour, preferring
   the vacating tail cell.

Death-proof but slow late-game (~185, 0 deaths on 20x10). It never returns `None`
when any legal move exists (only when genuinely no non-reversing move exists), so
the snake never coasts straight into its own body.
"""

from collections import deque

from typing_extensions import override

from ..game_rules import Direction, Position
from ._helpers import (
    blocked_cells,
    board_distance,
    body_after,
    legal_turns,
    neighbour,
)
from .base import DemoStrategy


class SafeBfsStrategy(DemoStrategy):
    """Shortest-path-to-food gated by a tail-reachability survival check."""

    # ---- board helpers (wrap- and wall-aware) ----
    def _step(self, pos: Position, direction: Direction) -> Position | None:
        return neighbour(self.game, pos, direction)

    def _dist(self, a: Position, b: Position) -> int:
        return board_distance(self.game, a, b)

    def _dir_between(self, a: Position, b: Position) -> Direction | None:
        """Exact, integer wrap- and wall-aware single-step direction from a to b.

        Returns the Direction d with step(a, d) == b, or None if not adjacent.
        """
        for d in Direction:
            if self._step(a, d) == b:
                return d
        return None

    # ---- BFS over the board ----
    def _bfs(
        self, start: Position, goal: Position, blocked: set[Position]
    ) -> list[Position]:
        """Parent-pointer BFS; returns the cell path start..goal or [] if none.

        ``goal`` is always reachable-as-target even if it sits in ``blocked``
        (the food may sit on a cell the vacating tail just left).
        """
        if start == goal:
            return [start]
        parent: dict[Position, Position | None] = {start: None}
        q = deque([start])
        while q:
            cur = q.popleft()
            for d in Direction:
                nb = self._step(cur, d)
                if nb is None or nb in parent:
                    continue
                if nb in blocked and nb != goal:
                    continue
                parent[nb] = cur
                if nb == goal:
                    # reconstruct
                    path = []
                    n = nb
                    while n is not None:
                        path.append(n)
                        n = parent[n]
                    return path[::-1]
                q.append(nb)
        return []

    def _can_reach(
        self, start: Position, goal: Position, blocked: set[Position]
    ) -> bool:
        """True if goal is reachable from start through unblocked cells."""
        if start == goal:
            return True
        return bool(self._bfs(start, goal, blocked))

    def _flood_fill_size(self, start: Position, blocked: set[Position]) -> int:
        """Count cells reachable from start over the free board (start counts)."""
        seen = {start}
        stack = [start]
        while stack:
            c = stack.pop()
            for d in Direction:
                nb = self._step(c, d)
                if nb is not None and nb not in seen and nb not in blocked:
                    seen.add(nb)
                    stack.append(nb)
        return len(seen)

    # ---- safety checks ----
    def _is_safe_after_path(self, snake: list[Position], path: list[Position]) -> bool:
        """Simulate walking the WHOLE food path, then confirm the resulting
        snake can still reach its own tail.

        ``path[0]`` is the head, ``path[-1]`` is the food. Only the final cell
        grows the snake; every earlier step vacates the tail, once the snake has
        grown in to its starting length.
        """
        body = list(snake)  # head first, tail last
        growth = self.game.pending_growth
        for i in range(1, len(path)):
            cell = path[i]
            ate = i == len(path) - 1  # only the final cell is food
            body.insert(0, cell)
            if ate:
                continue
            if growth:
                growth -= 1
            else:
                body.pop()
        new_head, new_tail = body[0], body[-1]
        # After eating, next step the tail will vacate, so model it as a
        # reachable target rather than a permanent obstacle.
        return self._can_reach(new_head, new_tail, blocked=set(body[:-1]))

    @override
    def get_next_direction(self) -> Direction | None:
        g = self.game
        snake = g.snake
        head = snake[0]
        food = g.food

        legal = legal_turns(g)
        if not legal:
            return None

        # 1) Shortest food path on the "will-be-free" board (tail modelled free,
        #    unless it stays put while the snake grows in).
        path = self._bfs(head, food, blocked=blocked_cells(g, False))
        if len(path) >= 2:
            first_dir = self._dir_between(head, path[1])
            if (
                first_dir is not None
                and first_dir in legal
                and self._is_safe_after_path(snake, path)
            ):
                return first_dir
            # else: fall through to survival (path unsafe or first step illegal)

        # 2) Survival move: keep the (future) tail reachable, then maximise
        #    reachable free space, then break ties toward food so the snake
        #    resumes progress instead of stalling/looping when boxed.
        best_dir: Direction | None = None
        best_score: tuple[int, int, int] | None = None
        for d in legal:
            nxt = self._step(head, d)
            if nxt is None:
                continue  # a wall
            grew = nxt == food
            blocked = blocked_cells(g, grew)
            if nxt in blocked:
                continue  # would collide (tail-vacate aware)
            space = self._flood_fill_size(nxt, blocked)
            new_body = body_after(g, nxt, grew)
            reach_tail = self._can_reach(
                new_body[0], new_body[-1], blocked=set(new_body[:-1])
            )
            score = (1 if reach_tail else 0, space, -self._dist(nxt, food))
            if best_score is None or score > best_score:
                best_score = score
                best_dir = d
        if best_dir is not None:
            return best_dir

        # 3) Last resort: any legal non-colliding neighbour, preferring the
        #    vacating tail cell.
        for d in legal:
            nxt = self._step(head, d)
            if nxt is not None and nxt not in blocked_cells(g, nxt == food):
                return d
        return legal[0]  # truly trapped; emit a legal move anyway
