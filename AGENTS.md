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

Every checkout — the primary one and each linked worktree — owns an independent `.venv`, so
run setup inside the assigned checkout. Review the tracked `.envrc` first, then:

```bash
direnv allow .                    # Approve this checkout only, after reviewing .envrc
uv sync --locked                  # Install exactly the locked dependencies
```

`.envrc` is tracked and secret-free: it optionally sources an ignored `.envrc.local`, points
`UV_PROJECT_ENVIRONMENT` at this checkout's own `.venv`, and adds that environment's `bin`
directory to `PATH`. direnv approval is manual and per path and never propagates, so review
and approve again in every linked worktree instead of assuming pool-wide or inherited trust.
Where direnv is unavailable, review `.envrc` in that checkout, then export
`UV_PROJECT_ENVIRONMENT="$PWD/.venv"` in the current shell so uv still resolves to that
checkout's environment; repeat this manual setup separately for every checkout.

`uv sync --locked` installs exactly what `uv.lock` records and fails instead of silently
relocking, matching the `--locked` semantics the pre-commit hooks and quality gate use. Do
not upgrade or relock dependencies as a side effect of setup; a lockfile change is its own
task.

Optional human or machine settings belong in the ignored `.envrc.local`. It is never
committed and never copied into a linked worktree, so it is not part of the shared contract.
Snek's development, test, lint, and quality commands need no project secrets: a missing
`.envrc.local` is expected, and nothing should be copied in to supply one.

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
  the splash on startup; owns the current immutable configuration, live `Game`, and selected
  demo strategy name. `settings` / `apply_settings()` read and replace the config and strategy
  together for the settings screen.
- **`cli.py`**: `main()`, the console entry point (`uv run snek`). Parses speed, sizing,
  logical-grid cap, visual scale, smoothing, walls, and demo-strategy options into a
  validated `GameConfig`.
- **`screens.py`**: the screens-as-states UI — `SplashScreen`, `SettingsModal`, `GameScreen`
  (the game loop + side panel), `PauseModal`, the scrollable `DiagnosticsModal`, and
  `GameOverModal`, plus the `SnakeView` board and the `SidePanel` / `StatDisplay` panel widgets.
- **`settings.py`**: framework-free settings rows for `SettingsModal`. `Settings` pairs the
  `GameConfig` with the demo strategy; each `SettingRow` offers fixed choices and steps through
  them, writing back through `dataclasses.replace` so `GameConfig` validates every change.
- **`game.py`**: core game logic and state (`Game`), plus `StepResult` — the frozen
  model→view contract returned by `Game.step()`.
- **`game_rules.py`**: pure game mechanics — movement (`next_position` wraps, or returns None
  at a wall), collision detection.
- **`rendering.py`**: framework-free board sizing and Rich `Segment` rendering. Separates
  logical game dimensions from visual cell scale and frames capped boards.
- **`sprites.py`**: cached Pillow/Rich Pixels food-sprite construction. World sprite IDs map
  to coloured tiles; scale-one rendering falls back to Unicode glyphs.
- **`clipboard.py`**: non-blocking diagnostics-copy support. Tries a platform clipboard
  subprocess with timeout/cancellation cleanup, then falls back to Textual's OSC 52 copy.
- **`demo/`**: pluggable demo drivers. `__init__.py` owns the strategy registry, default, and
  factory; `base.py` defines their contract; `greedy.py`, `safe_bfs.py`, `floodfill.py`, and
  `hamiltonian.py` provide the CLI-selectable implementations. `floodfill` is the default.
- **`timing.py`**: `StepClock`, the framework-free fixed-step accumulator that decides how
  many model steps each wake runs (and how far the next step has progressed), and
  `next_wake_delay()`, which says when the loop should wake next.
- **`worlds.py`**: world/theme progression (`WorldPath`) — tracks the current world and hands
  out themed food symbols.
- **`themes.py`**: per-world Textual themes (colors) and Unicode symbol sets.
- **`figlet.py`**: `FigletText`, the in-repo ASCII-art title widget (recolors on theme change
  by overriding `notify_style_update`).
- **`config.py`**: immutable, validated `GameConfig` values for timing, layout, progression,
  input buffering, and render glyphs.
- **`styles.css`**: Textual layout, compact-terminal breakpoints, modal sizing, and theme-token
  styling.

### Board edges

The board wraps around by default: the snake leaves one edge and enters the opposite one.
With `config.walls` (`--walls`) the edges are solid and moving off the board ends the game.
Every move goes through `GameRules.next_position`, and the demo strategies reach it through
`demo/_helpers.neighbour`, which returns None for a wall that callers treat as blocked. The
Hamiltonian strategy validates its cycle against the same rule, so on a walled board it uses a
cycle without wrap edges (one exists iff the cell count is even).

### Game Progression System

The game uses a world-based progression system where:
- Every `symbols_per_world` foods consumed (10 by default, see `config.py`) advances to the
  next world
- Each world has its own Textual theme (colors) and Unicode symbol set for food

### State & data flow

State is the **Textual screen stack**, not a separate state machine — each state is a screen:
`SplashScreen` → `GameScreen` → (`PauseModal` / `DiagnosticsModal` / `GameOverModal`),
navigated with `push_screen` / `pop_screen`; S on the splash pushes `SettingsModal`. Splash,
game, and pause are registered screens; settings, diagnostics, and game-over are fresh instances
so their displayed state cannot go stale.

Settings are session-only and reachable only from the splash, so no game is running when they
change. `apply_settings()` replaces `app.config` and the live `Game`'s config at once; the next
`start_new_game()` resets the game with it and calls `SnakeView.relayout()`, which
re-establishes the logical grid only if a layout setting (sizing, scale, grid cap, walls)
changed since the grid was last established.

Within the game loop:
1. `GameScreen._on_frame` feeds the elapsed wall time into a `StepClock` and runs one model
   step for each `current_interval` that has come due, re-reading the interval before every
   step. It then draws and calls `_arm()`, the only place that creates the loop timer
   (`self.timer`): a one-shot at the next step's exact deadline or, while interpolating, the
   next substep boundary (`timing.next_wake_delay`), and never closer than a frame except to
   meet a deadline. Exact wakes keep steps and increments evenly spaced; a fixed 60 Hz grid made
   gaps alternate by a frame. Pausing credits the time already waited and stops the timer;
   resuming re-arms and discards the paused time; game over stops it. Textual queues timer
   callbacks, so stopping a timer cannot recall a wake it already queued: each wake carries the
   `_generation` it was armed in, `_disarm()` bumps it, and `_on_wake` ignores stale wakes.
   `GameScreen.tick()` runs exactly one step and redraws it whole without touching timers;
   tests call `_disarm()` (not `timer.stop()`) and then advance by hand.
2. Each step, in demo mode, first asks the selected `DemoStrategy` for a direction, then calls
   `Game.step()`, which returns a `StepResult` describing the consequences (moved / ate food /
   world changed / game over). The view reacts to those flags rather than inferring model
   deltas.
3. `Game` owns world progression and speed via `WorldPath` and `current_interval`. A world change
   updates the Textual theme; game-over stops the frame timer and pushes a fresh modal.
4. The stats panel has one source of truth: `GameScreen` holds display-ready string
   reactives (`world_name`, `progress`, `foods_label`, `speed_label`), each `data_bind`'d
   (parent → child, read-only) to a `StatDisplay` in the `SidePanel`. After a frame's steps,
   `_sync_reactives()` runs once and the board refreshes once; the bindings propagate to the
   panel.

### Layout and rendering policy

- The **logical grid** is model state and fixes game difficulty; the **cell scale** is visual.
  `SnakeView` calls `compute_layout()` on its first valid layout and establishes the model grid
  once. Later viewport resizes call `fit_grid_scale()` and never rewrite snake or food coordinates.
- In `cap` mode, the grid grows only to `max_grid_*` and cells scale up to `cell_scale`, so larger
  terminals may letterbox a consistently sized game. In `fill` mode, `cell_scale` is fixed and the
  initial logical grid grows to fill the viewport.
- The frame is dim on a wrapping board and drawn only when capped with room to spare. With walls
  it is heavy and full intensity, and `SnakeView` reserves room for it in both sizing modes.
- The supported UI floor is 80×24. Below it, model invariants remain valid and scale never drops
  below one, but Textual may clip interface or board content.
- `SnakeView` uses Textual's Line API: `render_line()` centres and frames the board itself and
  delegates each board row to the pure `render_board_row()` in `rendering.py`. Food is a cached
  pixel sprite when enabled and scale permits, otherwise the world's Unicode glyph.
- Lines are drawn from a `BoardState` snapshot, not the live game. After each wake,
  `SnakeView.update_board()` takes a new snapshot and refreshes only the changed cells' regions, so
  Textual re-renders those lines and writes only those cells. Call `update_board()` after model
  steps; a plain full `refresh()` re-snapshots the live game drawn whole (use it after resets or
  direct model edits, as tests do).
- Movement is interpolated. The drawing trails the model by up to one step: `Game.step()` reports
  the new head, the vacated tail cell and their directions in `StepResult`, and
  `rendering.motion_cells()` turns those plus the clock's progress into part-filled cells (whole
  columns across, `▀`/`▄` half rows vertically, `2*scale` increments either way) that keep the
  visible length constant. The screen passes the step to `update_board()` only while
  interpolating: `smooth_motion` is on (`--no-smooth` turns it off), the glyphs are the default
  blocks, the step spans at least two frames, and exactly one step ran in the wake. Otherwise
  cells are drawn whole, and game over settles the board whole.

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
