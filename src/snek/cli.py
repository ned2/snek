"""Console entry point for the Snek game."""

import argparse
from dataclasses import replace

from .app import SnakeApp
from .config import default_config
from .demo import DEFAULT_STRATEGY, STRATEGIES

# The default starting speed, expressed in the same moves-per-second units the
# `--speed` flag (and the in-game stats panel) use. Derived from the config's
# interval so the two never drift apart.
DEFAULT_SPEED = 1.0 / default_config.initial_speed_interval


def _positive_speed(value: str) -> float:
    """Parse `--speed` as a positive moves-per-second float (argparse type)."""
    try:
        speed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number")
    if speed <= 0:
        raise argparse.ArgumentTypeError("speed must be greater than 0")
    return speed


def _build_parser() -> argparse.ArgumentParser:
    """Build the `snek` argument parser (factored out so it can be unit-tested)."""
    parser = argparse.ArgumentParser(
        prog="snek",
        description="Snek — a terminal Snake game with progressive Unicode worlds.",
    )
    parser.add_argument(
        "--speed",
        type=_positive_speed,
        default=DEFAULT_SPEED,
        metavar="MOVES_PER_SEC",
        help=(
            "starting snake speed in moves per second; higher is faster. The "
            "snake still accelerates as it eats (default: %(default)s)"
        ),
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
    # `--speed` is moves per second; the game model works in seconds per move.
    config = replace(default_config, initial_speed_interval=1.0 / args.speed)
    SnakeApp(config=config, demo_strategy=args.demo_strategy).run()
