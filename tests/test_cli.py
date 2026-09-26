"""Tests for the `snek` CLI: the `--speed` and `--demo-strategy` selectors."""

import pytest

from snek.app import SnakeApp
from snek.cli import _build_parser, main
from snek.config import default_config
from snek.demo import DEFAULT_STRATEGY, STRATEGIES
from snek.modes import CUSTOM, DEFAULT_MODE, MODES, Settings, mode_of
from snek.screens import GameScreen


def test_parser_speed_defaults_to_the_mode():
    """With no flag, the speed is the mode's: None until `main` applies it."""
    assert _build_parser().parse_args([]).speed is None


def test_parser_accepts_explicit_speed():
    """A positive `--speed` is parsed as a float."""
    assert _build_parser().parse_args(["--speed", "20"]).speed == pytest.approx(20.0)


@pytest.mark.parametrize("value", ["0", "-5", "abc", "", "nan", "inf", "501", "1e-309"])
def test_parser_rejects_non_positive_or_invalid_speed(value):
    """Unsafe, non-finite, and non-numeric speeds are rejected."""
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--speed", value])


def test_parser_accepts_maximum_safe_speed():
    maximum = 1.0 / default_config.min_speed_interval
    assert _build_parser().parse_args(["--speed", str(maximum)]).speed == maximum


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


def test_parser_demo_strategy_defaults_to_the_mode():
    """With no flag, the strategy is the mode's, which is the default strategy."""
    assert _build_parser().parse_args([]).demo_strategy is None


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
    """`--sizing` defaults to the mode's (None) and accepts cap/fill."""
    assert _build_parser().parse_args([]).sizing is None
    assert _build_parser().parse_args(["--sizing", "fill"]).sizing == "fill"


def test_parser_rejects_unknown_sizing():
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--sizing", "stretch"])


def test_parser_grid_parsing():
    assert _build_parser().parse_args(["--grid", "40x24"]).grid == (40, 24)
    minimum = f"{default_config.min_game_width}x{default_config.min_game_height}"
    assert _build_parser().parse_args(["--grid", minimum]).grid == (
        default_config.min_game_width,
        default_config.min_game_height,
    )


@pytest.mark.parametrize(
    "value",
    ["40", "40x", "axb", "40x0", "-4x4", "", "1x1", "9x10", "10x9"],
)
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


@pytest.mark.parametrize(
    ("argv", "smooth"), [([], True), (["--no-smooth"], False), (["--smooth"], True)]
)
def test_main_applies_smooth_motion_flag(monkeypatch, argv, smooth):
    """`--no-smooth` turns off movement interpolation."""
    captured = {}

    class FakeApp:
        def __init__(self, config=None, demo_strategy=None):
            captured["config"] = config

        def run(self):
            pass

    monkeypatch.setattr("snek.cli.SnakeApp", FakeApp)
    main(argv)
    assert captured["config"].smooth_motion is smooth


@pytest.mark.parametrize(
    ("argv", "walls"),
    [
        ([], True),
        (["--no-walls"], False),
        (["--mode", "arena"], False),
        (["--mode", "arena", "--walls"], True),
    ],
)
def test_main_applies_walls_flag(monkeypatch, argv, walls):
    """Walls come from the mode (Classic has them); `--[no-]walls` overrides."""
    captured = {}

    class FakeApp:
        def __init__(self, config=None, demo_strategy=None):
            captured["config"] = config

        def run(self):
            pass

    monkeypatch.setattr("snek.cli.SnakeApp", FakeApp)
    main(argv)
    assert captured["config"].walls is walls


@pytest.mark.parametrize(
    ("argv", "food_type"),
    [
        ([], "diamond"),
        (["--food", "glyphs"], "glyphs"),
        (["--food", "sprites", "--scale", "2"], "sprites"),
        (["--mode", "arena"], "glyphs"),
        (["--mode", "arcade", "--food", "diamond"], "diamond"),
    ],
)
def test_main_applies_food_flag(monkeypatch, argv, food_type):
    assert _launch(monkeypatch, argv).get("food_type") == food_type


def test_parser_rejects_unknown_food():
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--food", "cake"])


@pytest.mark.parametrize(
    ("argv", "length"),
    [
        ([], 8),
        (["--mode", "arena"], 3),
        (["--start-length", "1"], 1),
        (["--mode", "arena", "--start-length", "10"], 10),
    ],
)
def test_main_applies_start_length_flag(monkeypatch, argv, length):
    assert _launch(monkeypatch, argv).get("start_length") == length


@pytest.mark.parametrize("value", ["0", "11", "-1", "two", "2.5"])
def test_parser_rejects_start_lengths_off_the_settings_row(value):
    """Only 1 to 10, the settings screen's choices."""
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--start-length", value])


def test_main_demo_strategy_comes_from_the_mode(monkeypatch):
    assert _launch(monkeypatch, []).demo_strategy == DEFAULT_STRATEGY
    chosen = _launch(monkeypatch, ["--demo-strategy", "greedy"])
    assert chosen.demo_strategy == "greedy"
    assert mode_of(chosen) == CUSTOM


def test_main_reports_invalid_flag_combinations_as_usage_errors(monkeypatch, capsys):
    """Flags valid alone but not together exit like argparse, before the TUI."""

    def no_app(*args, **kwargs):
        raise AssertionError("the app must not start")

    monkeypatch.setattr("snek.cli.SnakeApp", no_app)
    with pytest.raises(SystemExit) as exit_info:
        main(["--food", "sprites", "--scale", "1"])
    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "usage: snek" in err
    assert "food sprites need a cell scale of at least 2, got 1" in err


def _launch(monkeypatch, argv: list[str]) -> Settings:
    """The config and demo strategy `main` would launch the app with."""
    captured = {}

    class FakeApp:
        def __init__(self, config=None, demo_strategy=None):
            captured["settings"] = Settings(base=config, demo_strategy=demo_strategy)

        def run(self):
            pass

    monkeypatch.setattr("snek.cli.SnakeApp", FakeApp)
    main(argv)
    return captured["settings"]


def test_default_launch_is_classic(monkeypatch):
    settings = _launch(monkeypatch, [])
    assert mode_of(settings) == DEFAULT_MODE.name
    assert settings.to_config() == default_config


@pytest.mark.parametrize("mode", MODES, ids=lambda mode: mode.key)
def test_mode_flag_applies_the_mode(monkeypatch, mode):
    assert mode_of(_launch(monkeypatch, ["--mode", mode.key])) == mode.name


def test_flags_override_the_mode(monkeypatch):
    """Any flag that changes a mode's value makes it Custom; one that matches it
    leaves the mode in force."""
    for argv in (
        ["--mode", "arcade", "--scale", "3"],
        ["--speed", "20"],
        ["--no-smooth"],
        ["--start-length", "3"],
    ):
        assert mode_of(_launch(monkeypatch, argv)) == CUSTOM, argv
    for argv, mode in (
        (["--mode", "arena", "--no-walls"], "Arena"),
        (["--speed", "10", "--smooth", "--start-length", "8"], "Classic"),
    ):
        assert mode_of(_launch(monkeypatch, argv)) == mode, argv


def test_sprites_alone_needs_a_bigger_scale_than_classic(monkeypatch, capsys):
    """Classic draws cells at scale one, so `--food sprites` alone is refused
    rather than raising the scale; `--mode arcade` is the designed alternative."""
    with pytest.raises(SystemExit):
        _launch(monkeypatch, ["--food", "sprites"])
    assert "food sprites need a cell scale of at least 2" in capsys.readouterr().err
