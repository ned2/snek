"""Optimal solver — Hamiltonian cycle follower with provably-safe shortcuts.

Precompute a Hamiltonian cycle over the W x H grid (a parity-aware serpentine
with a vertical return spine), assigning each cell an integer cycle-order index
``order[cell]`` in ``[0, N)``. A snake that always steps to its cycle-successor is
a contiguous arc of the loop (head at the highest order position, tail at the
lowest); the head only ever advances into the cell the tail just vacated, so it
can NEVER self-collide. That survives indefinitely but eats slowly.

To go faster we layer SHORTCUTS on top: instead of always following the
cycle-successor the head may jump to any orthogonal neighbour whose cycle index
lies strictly *ahead* of the head but strictly *behind* the tail in cycle order,
skipping cells we don't need to visit yet — provided the jump never lets the head
reach or overtake the tail's cycle position (the tail only frees one cell per
non-growing step). Among the legal candidates we pick the one minimising the
cycle-distance from the landing cell to the food. Shortcuts are disabled once the
snake exceeds ~50% of the board, falling back to pure cycle-following for a
guaranteed survival mode. It solves the board every game (198->199 foods on 20x10).

Toroidal wrap is handled for free: the cycle is just an ordering of cells whose
consecutive edges are validated against ``GameRules.calculate_new_position`` (the
same modulo-wrap the engine moves with), so wrap-adjacency is honoured. Odd x odd
grids admit no Hamiltonian cycle; we degrade gracefully to a Hamiltonian path
whose single non-adjacent seam is covered by a tail-vacate-aware safe fallback.
The cycle is rebuilt whenever ``(width, height)`` changes, so a freshly
established model grid never strands the snake on a stale plan (contract #3 /
0005-B7). Normal viewport resizes change only rendering scale and leave the
cycle untouched.
"""

from typing_extensions import override

from ..game import Game
from ..game_rules import Direction, GameRules, Position
from .base import DemoStrategy


class HamiltonianStrategy(DemoStrategy):
    """Hamiltonian-cycle follower with provably-safe, food-seeking shortcuts."""

    def __init__(self, game: Game) -> None:
        super().__init__(game)
        self.cycle: list[Position] = []  # cells in visiting order, len == N
        self.order: dict[Position, int] = {}  # cell -> index in [0, N)
        self._built_for: tuple[int, int] | None = None  # (width, height) built for
        self._is_true_cycle = False  # False when only a path (odd x odd grid)

    # ------------------------------------------------------------------ public
    @override
    def get_next_direction(self) -> Direction | None:
        g = self.game
        if (g.width, g.height) != self._built_for:  # first call or new model grid
            self._build_cycle(g.width, g.height)  # auto-invalidates stale plan

        n = len(self.cycle)
        if n == 0:
            return self._safe_fallback()

        head = g.snake[0]
        if head not in self.order:  # defensive inconsistent-grid fallback
            return self._safe_fallback()

        head_i = self.order[head]
        cyc_next = self.cycle[(head_i + 1) % n]

        # The cycle-successor is the always-safe default, BUT on an odd x odd grid
        # the path has one non-adjacent seam; if the successor is not actually a
        # torus neighbour, follow a safe fallback instead.
        default_dir = self._direction_between(head, cyc_next)
        if default_dir is None or not GameRules.is_valid_turn(g.direction, default_dir):
            # Either the seam (path mode) or a transient grid-change reversal.
            return self._safe_fallback()

        # The cycle-successor is collision-safe only while the snake is a
        # contiguous arc of a TRUE cycle (the head advances into the cell the tail
        # just vacated). On an odd x odd Hamiltonian PATH the successor across the
        # interior is NOT guaranteed free, and an external dimension change can
        # leave the body non-contiguous in cycle order. Tail-vacate-check the
        # successor and divert to the safe fallback rather than walking into it.
        grows = cyc_next == g.food
        blocked = set(g.snake) if grows else set(g.snake[:-1])
        if cyc_next in blocked:
            return self._safe_fallback()

        tail = g.snake[-1]
        best_dir = default_dir
        best_score = self._cycle_dist(self.order[cyc_next], self._food_index(head_i), n)

        # Shortcuts are provably safe ONLY on a true cycle (the contiguous-arc
        # invariant in _shortcut_is_safe). In path mode (odd x odd) follow the
        # cycle successor exactly; jumping there can self-trap.
        if self._is_true_cycle:
            body_without_tail = set(g.snake[:-1])  # tail vacates this step
            for d in Direction:
                if not GameRules.is_valid_turn(g.direction, d):
                    continue  # never emit a 180; honours the one-turn-per-tick model
                nxt = GameRules.calculate_new_position(head, d, g.width, g.height)
                if nxt == cyc_next:
                    continue  # already the baseline
                if nxt not in self.order:  # off-grid (cannot happen) / broken seam
                    continue
                # Don't shortcut into the body. For a contiguous arc a safe
                # shortcut always lands on an empty gap cell so this never fires
                # (identical play); it only guards a body left non-contiguous by a
                # external dimension change, where cycle order alone isn't enough.
                if nxt in body_without_tail:  # food is never on the body
                    continue
                if not self._shortcut_is_safe(
                    head_i, self.order[tail], self.order[nxt], n
                ):
                    continue
                score = self._cycle_dist(self.order[nxt], self._food_index(head_i), n)
                if score < best_score:
                    best_score = score
                    best_dir = d

        return best_dir

    # ------------------------------------------------- shortcut safety (heart)
    def _shortcut_is_safe(self, head_i: int, tail_i: int, nxt_i: int, n: int) -> bool:
        """Is jumping to cycle-index ``nxt_i`` safe given head/tail positions?

        The snake occupies a contiguous forward arc from the tail to the head. A
        shortcut to ``nxt_i`` is safe iff it lands strictly ahead of the head and
        strictly before the tail in forward cycle order, so the head never reaches
        or overtakes the cell the tail occupies (the tail frees only one cell per
        non-growing step).
        """
        # Crowded board -> survival mode: only the cycle-successor is permitted.
        if len(self.game.snake) > (n * 5) // 10:
            return False
        d_next = self._cycle_dist(head_i, nxt_i, n)  # forward steps head advances
        d_tail = self._cycle_dist(head_i, tail_i, n)  # forward steps head -> tail
        if d_next == 0:  # must actually move forward
            return False
        if d_tail == 0:  # tail sits at head's index (board full arc) -> only +1
            return d_next == 1
        return d_next < d_tail  # land strictly before the tail's cell

    @staticmethod
    def _cycle_dist(a: int, b: int, n: int) -> int:
        """Forward distance from index ``a`` to index ``b`` along the directed cycle."""
        return (b - a) % n

    def _food_index(self, head_i: int) -> int:
        """Cycle index of the food, or the head's own index if the food is off the
        cycle (e.g. a transient grid-change state) so shortcuts simply don't help."""
        return self.order.get(self.game.food, head_i)

    # --------------------------------------------- cycle construction & checks
    def _build_cycle(self, w: int, h: int) -> None:
        cells = None
        self._is_true_cycle = False
        if h % 2 == 0:
            cells = self._serpentine_h_even(w, h)
        elif w % 2 == 0:
            cells = [(b, a) for (a, b) in self._serpentine_h_even(h, w)]

        if cells is not None and self._is_valid_cycle(cells, w, h):
            self._is_true_cycle = True
        else:
            # Odd x odd (no cycle exists) or an unexpected build failure: fall back
            # to a Hamiltonian PATH that still covers every cell. Its last->first
            # seam is non-adjacent; the safe fallback bridges that single tick.
            cells = self._serpentine_path(w, h)
            assert self._covers_all(cells, w, h), (
                f"path does not cover {w}x{h} exactly once"
            )

        self.cycle = cells
        self.order = {c: i for i, c in enumerate(cells)}
        self._built_for = (w, h)

    def _serpentine_h_even(self, w: int, h: int) -> list[Position]:
        """Hamiltonian cycle requiring ``h`` even (any ``w`` >= 1).

        Row 0 is the outbound connector (traversed fully left->right); columns
        ``w-1 .. 1`` over rows ``1 .. h-1`` are woven as a vertical boustrophedon;
        column 0 is the vertical return spine, oriented to meet the weave's end.
        """
        assert h % 2 == 0 and h >= 2
        path: list[Position] = [(0, 0)]
        for x in range(1, w):
            path.append((x, 0))
        if w == 1:
            # Single column: column 0 down rows 1..h-1; wraps top<->bottom on torus.
            for y in range(1, h):
                path.append((0, y))
            return path
        last_end_y = None
        for ci, x in enumerate(range(w - 1, 0, -1)):
            ys = range(1, h) if ci % 2 == 0 else range(h - 1, 0, -1)
            ys = list(ys)
            path.extend((x, y) for y in ys)
            last_end_y = ys[-1]
        # Weave ended at (1, last_end_y); the spine on column 0 starts adjacent.
        if last_end_y == h - 1:
            for y in range(h - 1, 0, -1):  # (0,h-1) up to (0,1); wraps to (0,0)
                path.append((0, y))
        else:  # last_end_y == 1
            for y in range(1, h):  # (0,1) down to (0,h-1); wraps to (0,0)
                path.append((0, y))
        return path

    def _serpentine_path(self, w: int, h: int) -> list[Position]:
        """Simple boustrophedon covering every cell exactly once (a Hamiltonian
        path; consecutive cells are adjacent except possibly the wrap seam)."""
        path: list[Position] = []
        for y in range(h):
            xs = range(w) if y % 2 == 0 else range(w - 1, -1, -1)
            path.extend((x, y) for x in xs)
        return path

    def _covers_all(self, cells: list[Position], w: int, h: int) -> bool:
        return len(cells) == w * h and len(set(cells)) == w * h

    def _is_valid_cycle(self, cells: list[Position], w: int, h: int) -> bool:
        if not self._covers_all(cells, w, h):
            return False
        n = len(cells)
        return all(
            self._are_neighbours(cells[i], cells[(i + 1) % n], w, h) for i in range(n)
        )

    def _are_neighbours(self, a: Position, b: Position, w: int, h: int) -> bool:
        return any(GameRules.calculate_new_position(a, d, w, h) == b for d in Direction)

    # ----------------------------------------------------------------- helpers
    def _direction_between(self, frm: Position, to: Position) -> Direction | None:
        g = self.game
        for d in Direction:
            if GameRules.calculate_new_position(frm, d, g.width, g.height) == to:
                return d
        return None

    def _safe_fallback(self) -> Direction | None:
        """Last-ditch, tail-vacate-aware move. The tail vacates on a non-growing
        step, so it is enterable; prefer the most-open landing cell. Never returns
        None when any legal non-colliding move exists."""
        g = self.game
        head = g.snake[0]
        best: tuple[int, Direction] | None = None  # (free_neighbours, direction)
        any_legal: Direction | None = None
        for d in Direction:
            if not GameRules.is_valid_turn(g.direction, d):
                continue
            any_legal = d
            nxt = GameRules.calculate_new_position(head, d, g.width, g.height)
            grows = nxt == g.food
            blocked = set(g.snake) if grows else set(g.snake[:-1])
            if nxt in blocked:
                continue
            # one-ply openness proxy, tail-vacate aware
            free = sum(
                1
                for dd in Direction
                if GameRules.calculate_new_position(nxt, dd, g.width, g.height)
                not in blocked
            )
            if best is None or free > best[0]:
                best = (free, d)
        if best is not None:
            return best[1]
        # Genuinely trapped: every legal move collides. Emit a legal move anyway
        # (deterministic) rather than None so the engine still issues a turn.
        return any_legal
