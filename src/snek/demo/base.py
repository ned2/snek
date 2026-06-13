"""The demo-strategy interface and the shared correctness contract."""

from abc import ABC, abstractmethod

from ..game import Game
from ..game_rules import Direction


class DemoStrategy(ABC):
    """A demo-mode driver: constructed once with the live `Game`, queried each tick.

    Every concrete strategy must satisfy this correctness contract (a shared,
    parametrised test enforces it across the whole registry):

    1. **Legal-or-bust** (kills 0005/B1): return a `Direction` that passes
       `GameRules.is_valid_turn(game.direction, d)` whenever *any* non-reversing
       move exists. Return `None` **only** when no non-reversing move exists at
       all — never as a silent "no opinion" that makes the snake coast straight
       into its own body.
    2. **Tail-vacate aware** (kills 0005/B4): when testing whether a target cell
       is blocked, model the tail as *free* on a non-growing step — the engine
       checks collision against `snake[:-1]` unless the move eats. Use the shared
       helpers (`_helpers.blocked_cells`) so this is uniform.
    3. **Resize-tolerant** (kills 0005/B7): hold no grid-coordinate state that
       survives a `Game.resize`; rebuild any precomputed structure (e.g. a
       Hamiltonian cycle) when `(game.width, game.height)` changes.
    4. **Deterministic**: a pure function of game state (no RNG), so benchmarks
       are reproducible. Tie-break in a fixed order (the `Direction` enum order),
       never set-iteration order.
    """

    def __init__(self, game: Game) -> None:
        """Bind the strategy to the live game it will drive."""
        self.game = game

    @abstractmethod
    def get_next_direction(self) -> Direction | None:
        """Return the direction to turn this tick (see the class contract)."""
        ...
