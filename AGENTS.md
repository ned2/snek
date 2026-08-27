# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project Overview

Snek is a terminal-based Snake game built using the
[Textual](https://textual.textualize.io) framework. The game features progressive themes
with different Unicode characters that unlock as the player advances through worlds.

## Tracking & Notes

**Do not create or rely on a private agent memory store.** This project tracks durable
working context exclusively in the local issue tracker under `issues/` (see
`issues/README.md`) — research notes, plans, and design decisions all live there. If
something is worth remembering, record it in the relevant `issues/NNNN-*/` directory
instead.

Agent-facing rules and recurring gotchas belong in this file. Claude-Code-specific loading
notes belong in [CLAUDE.md](CLAUDE.md), which imports this file.

## Development Commands

**Setup and Installation:**

```bash
uv sync                           # Install dependencies
```

**Running the Application:**

```bash
uv run snek                       # Start the game
```

**Development Tools:**

```bash
uv run pytest                     # Run all tests
uv run pytest tests/test_game.py  # Run specific test file
uv run ruff check                 # Lint the codebase
uv run ruff format                # Format the codebase
uv run python scripts/check_quality.py  # Run the complete local quality gate
```

**Coverage Testing:**

```bash
uv run coverage run -m pytest     # Run tests with coverage
uv run coverage report            # Show coverage report in terminal
uv run coverage html              # Generate HTML coverage report in htmlcov/
uv run coverage erase             # Clear previous coverage data
```

**Development server (if using textual-dev):**

```bash
uv run textual run --dev snek.app:SnakeApp  # Run with dev tools
```

## Architecture

### Core Components

- **`app.py`**: `SnakeApp`, the Textual `App`. Registers the screens in `SCREENS` and pushes
  the splash on startup; owns the immutable configuration, live `Game`, and selected demo
  strategy name.
- **`cli.py`**: `main()`, the console entry point (`uv run snek`). Parses speed, sizing,
  logical-grid cap, visual scale, and demo-strategy options into a validated `GameConfig`.
- **`screens.py`**: the screens-as-states UI — `SplashScreen`, `GameScreen` (the game loop +
  side panel), `PauseModal`, the scrollable `DiagnosticsModal`, and `GameOverModal`, plus the
  `SnakeView` board and the `SidePanel` / `StatDisplay` panel widgets.
- **`game.py`**: core game logic and state (`Game`), plus `StepResult` — the frozen
  model→view contract returned by `Game.step()`.
- **`game_rules.py`**: pure game mechanics — movement, collision detection.
- **`rendering.py`**: framework-free board sizing and Rich `Segment` rendering. Separates
  logical game dimensions from visual cell scale and frames capped boards.
- **`sprites.py`**: cached Pillow/Rich Pixels food-sprite construction. World sprite IDs map
  to coloured tiles; scale-one rendering falls back to Unicode glyphs.
- **`clipboard.py`**: non-blocking diagnostics-copy support. Tries a platform clipboard
  subprocess with timeout/cancellation cleanup, then falls back to Textual's OSC 52 copy.
- **`demo/`**: pluggable demo drivers. `__init__.py` owns the strategy registry, default, and
  factory; `base.py` defines their contract; `greedy.py`, `safe_bfs.py`, `floodfill.py`, and
  `hamiltonian.py` provide the CLI-selectable implementations. `floodfill` is the default.
- **`worlds.py`**: world/theme progression (`WorldPath`) — tracks the current world and hands
  out themed food symbols.
- **`themes.py`**: per-world Textual themes (colors) and Unicode symbol sets.
- **`figlet.py`**: `FigletText`, the in-repo ASCII-art title widget (recolors on theme change
  by overriding `notify_style_update`).
- **`config.py`**: immutable, validated `GameConfig` values for timing, layout, progression,
  input buffering, and render glyphs.
- **`styles.css`**: Textual layout, compact-terminal breakpoints, modal sizing, and theme-token
  styling.

### Game Progression System

The game uses a world-based progression system where:
- Every `symbols_per_world` foods consumed (10 by default, see `config.py`) advances to the
  next world
- Each world has its own Textual theme (colors) and Unicode symbol set for food

### State & data flow

State is the **Textual screen stack**, not a separate state machine — each state is a screen:
`SplashScreen` → `GameScreen` → (`PauseModal` / `DiagnosticsModal` / `GameOverModal`),
navigated with `push_screen` / `pop_screen`. Splash, game, and pause are registered screens;
diagnostics and game-over are fresh instances so their displayed state cannot go stale.

Within the game loop:
1. In demo mode, `GameScreen.tick` first asks the selected `DemoStrategy` for a direction.
2. The interval timer calls `Game.step()`, which returns a `StepResult` describing the
   consequences (moved / ate food / world changed / game over). The view reacts to those flags
   rather than inferring model deltas.
3. `Game` owns world progression via `WorldPath`. A world change updates the Textual theme; eating
   restarts the interval at the model's new speed; game-over stops the timer and pushes a fresh
   modal.
4. The stats panel has one source of truth: `GameScreen` holds display-ready string
   reactives (`world_name`, `progress`, `foods_label`, `speed_label`), each `data_bind`'d
   (parent → child, read-only) to a `StatDisplay` in the `SidePanel`. `tick` calls
   `_sync_reactives()` once; the bindings propagate to the panel.

### Layout and rendering policy

- The **logical grid** is model state and fixes game difficulty; the **cell scale** is visual.
  `SnakeView` calls `compute_layout()` on its first valid layout and establishes the model grid
  once. Later viewport resizes call `fit_grid_scale()` and never rewrite snake or food coordinates.
- In `cap` mode, the grid grows only to `max_grid_*` and cells scale up to `cell_scale`, so larger
  terminals may letterbox a consistently sized game. In `fill` mode, `cell_scale` is fixed and the
  initial logical grid grows to fill the viewport.
- The supported UI floor is 80×24. Below it, model invariants remain valid and scale never drops
  below one, but Textual may clip interface or board content.
- `SnakeView.render()` delegates board construction to the pure helpers in `rendering.py`. Food is
  a cached pixel sprite when enabled and scale permits, otherwise the world's Unicode glyph.

### Diagnostics and clipboard flow

`?` pauses play and pushes a fresh `DiagnosticsModal`, whose scrollable body snapshots current
terminal, layout, config, model, and demo values. Its `C` action runs as an exclusive Textual worker
so clipboard subprocesses never block the UI. `clipboard.copy_text()` prefers the native platform
tool and reports whether it used that tool or the OSC 52 fallback.

## Code Conventions

- Follow PEP8 formatting guidelines
- Always use type hints for function arguments and return values
- Use standard Python types (`list`, `dict`, `tuple`) instead of `typing` module equivalents
- Use `textwrap.dedent()` for multiline strings to maintain proper indentation

## Testing

Tests are located in the `tests/` directory and use pytest with asyncio support. The
test configuration is in `pytest.ini` with verbose output and short tracebacks enabled.
