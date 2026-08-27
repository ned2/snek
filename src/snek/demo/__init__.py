"""Pluggable demo-mode AI strategies.

A small registry of interchangeable `DemoStrategy` implementations, each a
behaviourally-distinct way to drive the snake in demo mode. The
`--demo-strategy` CLI option selects a `STRATEGIES` registry entry and carries
that name through `SnakeApp` to `make_demo_ai`; omitting it uses
`DEFAULT_STRATEGY`. Empirical backing for the shortlist lives in
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
    """Construct the CLI-selected strategy, or the default when unnamed."""
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
