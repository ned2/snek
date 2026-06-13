"""Tests for the `snek` CLI: the `--speed` and `--demo-strategy` selectors."""

import pytest

from snek.app import SnakeApp
from snek.cli import DEFAULT_SPEED, _build_parser, main
from snek.config import default_config
from snek.demo import DEFAULT_STRATEGY, STRATEGIES
from snek.screens import GameScreen


def test_parser_default_speed_matches_config():
    """With no flag, `--speed` defaults to the config's starting moves-per-second."""
    assert _build_parser().parse_args([]).speed == DEFAULT_SPEED
    assert DEFAULT_SPEED == pytest.approx(1.0 / default_config.initial_speed_interval)


def test_parser_accepts_explicit_speed():
    """A positive `--speed` is parsed as a float."""
    assert _build_parser().parse_args(["--speed", "20"]).speed == pytest.approx(20.0)


@pytest.mark.parametrize("value", ["0", "-5", "abc", ""])
def test_parser_rejects_non_positive_or_invalid_speed(value):
    """Zero, negative, and non-numeric speeds are rejected (exit non-zero)."""
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--speed", value])


def test_main_translates_speed_into_interval(monkeypatch):
    """`main` converts moves-per-second into the model's seconds-per-move interval."""
    captured = {}

    class FakeApp:
        def __init__(self, config=None, demo_strategy=None):
            captured["config"] = config
            captured["demo_strategy"] = demo_strategy

        def run(self):
            pass

    monkeypatch.setattr("snek.cli.SnakeApp", FakeApp)
    main(["--speed", "20"])
    assert captured["config"].initial_speed_interval == pytest.approx(1.0 / 20.0)
    # Overriding speed must not disturb the other config fields.
    assert (
        captured["config"].speed_increase_factor == default_config.speed_increase_factor
    )


def test_app_starts_at_requested_speed():
    """A custom interval flows through to the game's starting speed."""
    config = SnakeApp().config
    fast = type(config)(initial_speed_interval=1.0 / 25.0)
    assert SnakeApp(config=fast).game.get_moves_per_second() == pytest.approx(25.0)


def test_parser_default_is_default_strategy():
    """With no flag, `--demo-strategy` defaults to the active default strategy."""
    assert _build_parser().parse_args([]).demo_strategy == DEFAULT_STRATEGY


@pytest.mark.parametrize("name", list(STRATEGIES))
def test_parser_accepts_each_registered_strategy(name):
    """Every registry key is a valid `--demo-strategy` choice."""
    assert _build_parser().parse_args(["--demo-strategy", name]).demo_strategy == name


def test_parser_rejects_unknown_strategy():
    """An unknown strategy is rejected by argparse (exits non-zero)."""
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--demo-strategy", "does-not-exist"])


def test_app_default_demo_strategy():
    """A plain app uses the default strategy."""
    assert SnakeApp().demo_strategy == DEFAULT_STRATEGY


def test_app_stores_demo_strategy():
    """The app records the selected strategy for the game screen to use."""
    assert SnakeApp(demo_strategy="hamiltonian").demo_strategy == "hamiltonian"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(STRATEGIES))
async def test_demo_mode_uses_selected_strategy(name):
    """Pressing D builds the strategy named by `--demo-strategy`; restart keeps it."""
    app = SnakeApp(demo_strategy=name)
    async with app.run_test() as pilot:
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        assert isinstance(app.screen.demo_ai, STRATEGIES[name])

        app.screen.restart_game()  # restart preserves the selected strategy
        assert isinstance(app.screen.demo_ai, STRATEGIES[name])


def test_parser_sizing_default_and_choices():
    """`--sizing` defaults to the config mode and accepts cap/fill."""
    assert _build_parser().parse_args([]).sizing == default_config.sizing_mode
    assert _build_parser().parse_args(["--sizing", "fill"]).sizing == "fill"


def test_parser_rejects_unknown_sizing():
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--sizing", "stretch"])


def test_parser_grid_parsing():
    assert _build_parser().parse_args(["--grid", "40x24"]).grid == (40, 24)


@pytest.mark.parametrize("value", ["40", "40x", "axb", "40x0", "-4x4", ""])
def test_parser_rejects_bad_grid(value):
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--grid", value])


def test_parser_scale_parsing():
    assert _build_parser().parse_args(["--scale", "2"]).scale == 2


@pytest.mark.parametrize("value", ["0", "-1", "two", "1.5"])
def test_parser_rejects_bad_scale(value):
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--scale", value])


def test_main_applies_sizing_grid_scale(monkeypatch):
    """`main` threads the layout flags onto the config."""
    captured = {}

    class FakeApp:
        def __init__(self, config=None, demo_strategy=None):
            captured["config"] = config

        def run(self):
            pass

    monkeypatch.setattr("snek.cli.SnakeApp", FakeApp)
    main(["--sizing", "fill", "--grid", "40x24", "--scale", "2"])
    config = captured["config"]
    assert config.sizing_mode == "fill"
    assert (config.max_grid_width, config.max_grid_height) == (40, 24)
    assert config.cell_scale == 2


def test_main_layout_defaults_match_config(monkeypatch):
    """Without layout flags, the config keeps its defaults."""
    captured = {}

    class FakeApp:
        def __init__(self, config=None, demo_strategy=None):
            captured["config"] = config

        def run(self):
            pass

    monkeypatch.setattr("snek.cli.SnakeApp", FakeApp)
    main([])
    config = captured["config"]
    assert config.sizing_mode == default_config.sizing_mode
    assert config.max_grid_width == default_config.max_grid_width
    assert config.cell_scale == default_config.cell_scale
