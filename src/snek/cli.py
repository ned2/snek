"""Console entry point for the Snek game."""

import argparse
import math
from dataclasses import replace

from .app import SnakeApp
from .config import MIN_SPRITE_SCALE, default_config, validate_dimensions
from .demo import DEFAULT_STRATEGY, STRATEGIES
from .modes import DEFAULT_MODE, MODES, apply_mode

# The default starting speed, expressed in the same moves-per-second units the
# `--speed` flag (and the in-game stats panel) use. Derived from the config's
# interval so the two never drift apart.
DEFAULT_SPEED = 1.0 / default_config.initial_speed_interval


def _positive_speed(value: str) -> float:
    """Parse `--speed` as a positive moves-per-second float (argparse type)."""
    try:
        speed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from None
    if not math.isfinite(speed) or speed <= 0:
        raise argparse.ArgumentTypeError("speed must be finite and greater than 0")
    max_speed = 1.0 / default_config.min_speed_interval
    if speed > max_speed:
        raise argparse.ArgumentTypeError(
            f"speed must not exceed {max_speed:g} moves per second"
        )
    if not math.isfinite(1.0 / speed):
        raise argparse.ArgumentTypeError("speed is too small to represent safely")
    return speed


def _positive_int(value: str) -> int:
    """Parse `--scale` as a positive integer (argparse type)."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer") from None
    if number < 1:
        raise argparse.ArgumentTypeError("scale must be at least 1")
    return number


def _grid_dims(value: str) -> tuple[int, int]:
    """Parse `--grid`, applying model rules and the UI's layout floor."""
    parts = value.lower().split("x")
    try:
        width, height = (int(part) for part in parts)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{value!r} must be WIDTHxHEIGHT, e.g. 36x20"
        ) from None
    try:
        validate_dimensions(width, height)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    if width < default_config.min_game_width or height < default_config.min_game_height:
        raise argparse.ArgumentTypeError(
            "grid must be at least "
            f"{default_config.min_game_width}x{default_config.min_game_height}"
        )
    return width, height


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
        "--mode",
        choices=[mode.key for mode in MODES],
        default=DEFAULT_MODE.key,
        help=(
            "a designed mix of the board options below, which override it. "
            + " ".join(f"{mode.key}: {mode.description}" for mode in MODES)
            + " (default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--sizing",
        choices=("cap", "fill"),
        default=None,
        help=(
            "how the board is sized: 'cap' keeps a fixed, consistent grid scaled "
            "to fill up to --scale; 'fill' grows the grid to fill the terminal at "
            "exactly --scale (default: from --mode)"
        ),
    )
    parser.add_argument(
        "--grid",
        type=_grid_dims,
        default=None,
        metavar="WIDTHxHEIGHT",
        help="logical grid cap for --sizing cap, e.g. 36x20 (default: from --mode)",
    )
    parser.add_argument(
        "--scale",
        type=_positive_int,
        default=None,
        metavar="N",
        help=(
            "cell magnification (k): the max in 'cap' mode, the exact size in "
            "'fill' mode; --sprites needs k>=2 (default: from --mode)"
        ),
    )
    parser.add_argument(
        "--sprites",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "draw food as pixel art instead of glyphs; needs --scale "
            f">={MIN_SPRITE_SCALE}, and a terminal big enough for the board at that "
            "scale, with 'cap' sizing using the whole --grid (default: from --mode)"
        ),
    )
    parser.add_argument(
        "--walls",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "make the board edges solid walls instead of wrapping around "
            "(default: from --mode)"
        ),
    )
    parser.add_argument(
        "--no-smooth",
        dest="smooth",
        action="store_false",
        help="move the snake a whole cell at a time instead of sliding between cells",
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
    parser = _build_parser()
    args = parser.parse_args(argv)
    # `--speed` is moves per second; the game model works in seconds per move.
    overrides: dict[str, object] = {
        "initial_speed_interval": 1.0 / args.speed,
        "smooth_motion": args.smooth,
    }
    # Board flags override the mode only where given.
    for field, value in (
        ("sizing_mode", args.sizing),
        ("cell_scale", args.scale),
        ("food_sprites", args.sprites),
        ("walls", args.walls),
    ):
        if value is not None:
            overrides[field] = value
    if args.grid is not None:
        overrides["max_grid_width"], overrides["max_grid_height"] = args.grid
    mode = next(mode for mode in MODES if mode.key == args.mode)
    try:
        config = replace(apply_mode(default_config, mode.name), **overrides)
    except ValueError as error:
        # Each flag parsed on its own, but together they are invalid.
        parser.error(str(error))
    SnakeApp(config=config, demo_strategy=args.demo_strategy).run()
