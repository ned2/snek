"""Console entry point for the Snek game."""

import argparse

from .app import SnakeApp
from .demo import DEFAULT_STRATEGY, STRATEGIES


def _build_parser() -> argparse.ArgumentParser:
    """Build the `snek` argument parser (factored out so it can be unit-tested)."""
    parser = argparse.ArgumentParser(
        prog="snek",
        description="Snek — a terminal Snake game with progressive Unicode worlds.",
    )
    parser.add_argument(
        "--demo-strategy",
        choices=sorted(STRATEGIES),
        default=DEFAULT_STRATEGY,
        metavar="STRATEGY",
        help=(
            "which algorithm drives the snake in demo mode (press D); "
            f"one of {', '.join(sorted(STRATEGIES))} (default: %(default)s)"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and launch the app."""
    args = _build_parser().parse_args(argv)
    SnakeApp(demo_strategy=args.demo_strategy).run()
