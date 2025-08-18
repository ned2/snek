# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in
this repository.

## Project Overview

Snek is a terminal-based Snake game built using the
[Textual](https://textual.textualize.io) framework. The game features progressive themes
with different Unicode characters that unlock as the player advances through worlds.

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

**Development server (if using textual-dev):**

```bash
textual dev snek.app:SnekApp  # Run with dev tools
```

## Architecture

### Core Components

- **`app.py`**: Main Textual application with `SplashView` and `SnekApp` classes
- **`game.py`**: Core game logic and state (`Game` class)
- **`state_manager.py`**: Game state transitions (`StateManager` class)
- **`game_rules.py`**: Game mechanics, movement, collision detection
- **`worlds.py`**: World/theme progression system (`WorldPath` class)
- **`themes.py`**: Unicode character themes and visual styling
- **`config.py`**: Game configuration and settings

### Game Progression System

The game uses a world-based progression system where:
- Every 5 foods consumed advances to the next world
- Each world has different theme colors and Unicode themes for food symbols

### Key Data Flow

1. `SnekApp` manages overall application state via `StateManager`
2. `Game` class handles core game logic and world progression
3. `WorldPath` tracks current world and provides themed symbols
4. Game state flows: SPLASH → PLAYING → PAUSED → PLAYING → GAME_OVER → back to SPLASH

## Code Conventions

- Follow PEP8 formatting guidelines
- Always use type hints for function arguments and return values
- Use standard Python types (`list`, `dict`, `tuple`) instead of `typing` module equivalents
- Use `textwrap.dedent()` for multiline strings to maintain proper indentation

## Testing

Tests are located in the `tests/` directory and use pytest with asyncio support. The
test configuration is in `pytest.ini` with verbose output and short tracebacks enabled.
