"""Pluggable demo-mode AI strategies.

A small registry of interchangeable `DemoStrategy` implementations, each a
behaviourally-distinct way to drive the snake in demo mode. Selection is
*implemented* (the `STRATEGIES` registry + a single `DEFAULT_STRATEGY` constant)
but not yet exposed to the user — the game always constructs the default via
`make_demo_ai`. Empirical backing for the shortlist lives in
`issues/0004-demo-ai-skill/results.md`.
"""

from ..game import Game
from .base import DemoStrategy
from .floodfill import FloodFillStrategy
from .greedy import GreedyStrategy
from .hamiltonian import HamiltonianStrategy
from .safe_bfs import SafeBfsStrategy

STRATEGIES: dict[str, type[DemoStrategy]] = {
    "greedy": GreedyStrategy,
    "safe-bfs": SafeBfsStrategy,
    "floodfill": FloodFillStrategy,
    "hamiltonian": HamiltonianStrategy,
}

DEFAULT_STRATEGY = "floodfill"


def make_demo_ai(game: Game, name: str | None = None) -> DemoStrategy:
    """Construct the active (or named) demo strategy.

    The eventual user-facing selector will pass `name`; today everything uses
    `DEFAULT_STRATEGY`.
    """
    return STRATEGIES[name or DEFAULT_STRATEGY](game)


__all__ = [
    "DEFAULT_STRATEGY",
    "STRATEGIES",
    "DemoStrategy",
    "FloodFillStrategy",
    "GreedyStrategy",
    "HamiltonianStrategy",
    "SafeBfsStrategy",
    "make_demo_ai",
]
