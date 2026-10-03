# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project Overview

Snek is a terminal Snake game built with [Textual](https://textual.textualize.io).
[README.md](README.md) describes how it plays; [docs/adr/](docs/adr/) records why it is built
the way it is (see [Design decisions](#design-decisions)).

## Tracking & Notes

Record durable context in the project's own files; never in a private agent memory store:

- **Working context** — research, plans, decisions in progress — goes in the local issue
  tracker under `issues/` (see `issues/README.md`). It is git-ignored and exists only in the
  primary checkout, so nothing in the repository may depend on it.
- **Settled design decisions** the code depends on go in an ADR under `docs/adr/`.
- **Anything a human player or contributor needs** goes in [README.md](README.md) or an ADR.
- **Agent rules and recurring gotchas** go in this file, which holds nothing else.
  Claude-Code-specific loading notes go in [CLAUDE.md](CLAUDE.md), which imports this file.

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
make quality                      # Run the complete local quality gate
make help                         # List the individual gate stages (check, test, audit, ...)
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

## Design decisions

`docs/adr/` holds one architecture decision record (ADR) per decision; its `README.md` lists
them and gives the format. Read the ADR before changing the area it covers: screens and
navigation, the model→view `StepResult`, the logical grid and cell scale, step timing, board
rendering, interpolated motion, modes and settings, worlds and pace, Classic's Nokia defaults,
or sprite food. A change that alters a recorded decision updates or supersedes its ADR in the
same change. A new decision that is hard to reverse, surprising without context, and the result
of a real trade-off gets a new ADR.

A change to player-facing behaviour (modes, worlds, controls, flags, settings) updates
[README.md](README.md) in the same change.

## Rules when changing code

**Model.** `Game` and `game_rules.py` stay free of Textual. A new consequence of a step goes
into `StepResult`, which the view reacts to; the view never infers it by comparing model state
before and after a step. Speed comes only from the world's pace.

**Moves and walls.** Every move goes through `GameRules.next_position`, which returns None at
a wall. Demo strategies reach it through `demo/_helpers.neighbour` and treat None as blocked.

**Grow-in.** The snake starts as one cell and unrolls to `start_length`; on those steps its tail
stays put (`Game.pending_growth`, `Game.tail_stays`). Demo strategies use
`demo/_helpers.tail_moves`, `blocked_cells`, `body_after` and `growth_after`, which account for
a staying tail.

**Settings and modes.** Modes are exhaustive, and `tests/test_modes.py` enforces it: a new
settings-screen field joins `MODE_FIELDS` and gets a value in every mode, apart from the
starting world, which no mode sets. A setting that changes the logical grid or how the board is
fitted joins `_layout_key` in `screens.py`, the only trigger for re-establishing the grid. An
invalid combination is rejected by `GameConfig`, never corrected by falling back or changing
another setting: the CLI turns it into an argparse usage error (exit 2) before the TUI starts,
and the settings screen shows it and blocks ENTER. Changing a Classic value means changing the
matching `GameConfig` default too.

**Screens.** A screen that shows a snapshot of state is pushed as a fresh instance each time;
only stateless or self-refreshing screens are registered in `SnakeApp.SCREENS`. The registered
`GameScreen` outlives each game: games start through `start_new_game()` / `restart_game()` and
leave through `leave_to_menu()`, which leaves the game paused so nothing re-arms the loop.

**Game loop.** `GameScreen._arm()` is the only place that creates the loop timer, and
`_disarm()` is the only reliable way to stop it. `hold_for_size()` (a terminal too small for
sprite food) stops the loop without pausing the model; it is a hold, distinct from a pause.

**Grid and resizes.** A resize only refits the cell scale. The logical grid and `Game.cell_scale`
change only through a reset before play (`GameScreen.establish_grid()`).

**Drawing.** After model steps, call `SnakeView.update_board()`, which refreshes only the
changed cells; after a reset or a direct model edit, call a full `refresh()`, which
re-snapshots the live game. Anything new that changes how a cell is drawn goes into
`BoardState` (or forces a full refresh), or Textual's cached lines go stale;
`test_partial_board_updates_match_a_full_render` and
`test_interpolated_updates_match_a_full_render` in `tests/test_app.py` catch a missed region.
Panel stats change through `GameScreen`'s string reactives (`_sync_reactives()`), which are
data-bound one way to the `StatDisplay` widgets.

**Terminal size.** The UI must work at 80×24; `tests/test_app.py` checks that the splash and
settings screens fit. Below that, model invariants still hold and the cell scale stays at
least 1.

**Clipboard.** Clipboard copies run as an exclusive Textual worker, keeping subprocesses off
the UI thread.

## Code Conventions

- Follow PEP8 formatting guidelines
- Always use type hints for function arguments and return values
- Use standard Python types (`list`, `dict`, `tuple`) instead of `typing` module equivalents
- Use `textwrap.dedent()` for multiline strings to maintain proper indentation

## Testing

Tests are located in the `tests/` directory and use pytest with asyncio support. The
test configuration is in `pytest.ini` with verbose output and short tracebacks enabled.

`GameConfig`'s defaults are Classic's: walls, a fixed world and an 8-cell grow-in. Model tests
opt out explicitly:

- a wrapping board: `walls=False`;
- world progression: `world_change="progress"`;
- a one-cell snake with no grow-in: `start_length=1`. Assigning `game.snake` also clears
  grow-in, giving a fixed-length snake.

A `Game` that no view established runs at cell scale 1, so its speed is its world's pace at
scale 1. Tests that need an exact step interval patch `snek.game.WORLD_PACES` or
`Game.current_interval` with `monkeypatch`.

To drive the game loop by hand, call `GameScreen._disarm()`, then `GameScreen.tick()`, which
runs exactly one step and redraws it whole. `_disarm()` also invalidates a wake Textual has
already queued, which `timer.stop()` cannot recall.
