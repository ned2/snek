# snek

Snake in the terminal. Built using the [Textual](https://textual.textualize.io) Rapid
Application Development framework.


## Dependencies

* Python 3.10+ (tested on Python 3.10, 3.11, 3.12, 3.13, 3.14)

## Installation

### From PyPI (recommended)

    pip install snek-tui

### Development

    uv sync
    uv run pre-commit install --install-hooks

The install command enables both the fast commit hooks and the complete pre-push quality gate for
this checkout. Commit hooks normalize repository hygiene, apply Ruff's safe lint fixes and
formatter, and run ty over the production code and maintenance scripts.

Run the same checks across every tracked file on demand:

    uv run pre-commit run --all-files

Run the complete pre-push gate directly:

    uv run python scripts/check_quality.py

The full gate verifies the lockfile, Ruff lint and formatting, ty, the test suite and branch
coverage floor, locked runtime dependencies, distribution contents, and isolated wheel and source
installation with CLI and headless application smoke tests. Direct runs check the current working
tree; the pre-push hook checks the exact revision being pushed in a temporary detached worktree.
Gate coverage data and build artifacts are temporary and do not replace a developer's local
coverage results. Dependency auditing queries the vulnerability service, and first-time hook setup
downloads the pinned hook environments, so those operations require network access.

## Usage

    snek

The supported minimum terminal size is **80 columns × 24 rows**. The game model remains safe if
the terminal is made smaller, but interface elements may be clipped.

### Controls

- **Arrow keys** or **WASD**: Move the snake
- **Space**: Start game / Pause/unpause the game / Restart after game over
- **D** (on the splash screen): Watch the snek play itself in demo mode
- **Enter**: Toggle sidebar visibility
- **Q**: Quit the game
