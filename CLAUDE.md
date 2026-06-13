# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in
this repository.

## Project Overview

Snek is a terminal-based Snake game built using the
[Textual](https://textual.textualize.io) framework. The game features progressive themes
with different Unicode characters that unlock as the player advances through worlds.

## Tracking & Notes

**Do not write to the agent memory store. Ever.** This project tracks durable context
exclusively in the local issue tracker under `issues/` (see `issues/README.md`) — research
notes, plans, and design decisions all live there as markdown. Never create or update files
under the `.claude/.../memory/` directory or a `MEMORY.md`. If something is worth remembering,
record it in the relevant `issues/NNNN-*/` directory instead.

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
textual dev snek.app:SnakeApp  # Run with dev tools
```

## Architecture

### Core Components

- **`app.py`**: `SnakeApp`, the Textual `App`. Registers the screens in `SCREENS` and pushes
  the splash on startup.
- **`cli.py`**: `main()`, the console entry point (`uv run snek`).
- **`screens.py`**: the screens-as-states UI — `SplashScreen`, `GameScreen` (the game loop +
  side panel), `PauseModal`, `GameOverModal`, plus the `SnakeView` board and the `SidePanel`
  / `StatDisplay` panel widgets.
- **`game.py`**: core game logic and state (`Game`), plus `StepResult` — the frozen
  model→view contract returned by `Game.step()`.
- **`game_rules.py`**: pure game mechanics — movement, collision detection.
- **`worlds.py`**: world/theme progression (`WorldPath`) — tracks the current world and hands
  out themed food symbols.
- **`themes.py`**: per-world Textual themes (colors) and Unicode symbol sets.
- **`figlet.py`**: `FigletText`, the in-repo ASCII-art title widget (recolors on theme change
  by overriding `notify_style_update`).
- **`demo_ai.py`**: `DemoAI` — drives the snake automatically in demo mode.
- **`config.py`**: `GameConfig` — tunable settings (speed, symbols-per-world, render glyphs).

### Game Progression System

The game uses a world-based progression system where:
- Every `symbols_per_world` foods consumed (10 by default, see `config.py`) advances to the
  next world
- Each world has its own Textual theme (colors) and Unicode symbol set for food

### State & data flow

State is the **Textual screen stack**, not a separate state machine — each state is a screen:
`SplashScreen` → `GameScreen` → (`PauseModal` / `GameOverModal`), registered in
`SnakeApp.SCREENS` and navigated with `push_screen` / `pop_screen` / `dismiss`.

Within the game loop:
1. `GameScreen.tick` (the interval timer) calls `Game.step()`, which returns a `StepResult`
   describing the consequences of the tick (moved / ate food / world changed / game over). The
   view *reacts* to those flags rather than sniffing model deltas.
2. `Game` owns world progression via `WorldPath`, which provides the themed food symbols.
3. The stats panel is a single source of truth: `GameScreen` holds display-ready string
   reactives (`world_name`, `progress`, `foods_label`, `speed_label`), each `data_bind`'d
   (parent → child, read-only) to a `StatDisplay` in the `SidePanel`. `tick` calls
   `_sync_reactives()` once; the bindings propagate to the panel.

## Code Conventions

- Follow PEP8 formatting guidelines
- Always use type hints for function arguments and return values
- Use standard Python types (`list`, `dict`, `tuple`) instead of `typing` module equivalents
- Use `textwrap.dedent()` for multiline strings to maintain proper indentation

## Testing

Tests are located in the `tests/` directory and use pytest with asyncio support. The
test configuration is in `pytest.ini` with verbose output and short tracebacks enabled.
