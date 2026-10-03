# snek

Snake in the terminal. Built using the [Textual](https://textual.textualize.io) Rapid
Application Development framework.


## Dependencies

* Python 3.10–3.14

## Installation

### From PyPI (recommended)

    pip install snek-tui

### Development

Each checkout owns its own `.venv`. The tracked `.envrc` is secret-free and keeps uv and direct
tool invocations anchored to that checkout. Review it, then approve it separately in every linked
worktree before setup:

    direnv allow .

Then install exactly the locked dependencies and the hooks:

    uv sync --locked
    uv run pre-commit install --install-hooks

Optional human or machine settings may go in the ignored `.envrc.local`; it is not copied into
linked worktrees. Snek's development, pytest, Ruff, and quality commands do not require project
secrets, so there is no external agent dotenv file in the project contract.

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

### Design decisions

The reasons behind Snek's design (how screens, timing, rendering, modes and worlds work, and the
alternatives that were rejected) are recorded as architecture decision records in
[docs/adr/](docs/adr/). Read the relevant one before changing an area it covers, and add one for a
new decision that is hard to reverse. Coding agents get their working rules from
[AGENTS.md](AGENTS.md).

## Usage

    snek

Snek opens on a splash screen in **Classic** mode, which plays like the original Nokia Snake.
Press ←/→ there to change mode, or start in one with `--mode`:

- **Classic** (`classic`): solid walls round a fixed 20×11 board drawn like the green-grey
  Nokia LCD, diamond food and an 8-cell snake.
- **Arcade** (`arcade`): big pixel-art food on a walled board that fills the terminal.
- **Arena** (`arena`): glyph food on a board that fills the terminal and wraps around: leave one
  edge and you come back in at the opposite one.
- **Pixel Arena** (`pixel-arena`): pixel-art food on a wrapping board that fills the terminal.

For example:

    snek --mode arena

A mode is just a set of settings. Change one of them, on the settings screen or with a flag, and
the splash shows **Custom** instead; set them back to a mode's values and it shows that mode again.

In every mode the snake starts as a single cell and unrolls to its starting length (8 in Classic,
3 in the other modes), as in Nokia Snake.

Every game is played in one of nine worlds. Like Nokia Snake's levels, the world sets the snake's
pace and the points each food scores (1 in world 1, up to 9 in world 9), and filling the board
scores a 100-point bonus. Your score shows in the side panel and on the game-over screen. Classic
stays in the world you start in; the other modes move on to the next world after each set of foods
(how many depends on the mode), each world in its own colours, and stay in world 9 once there.
Choose the starting world with ↑/↓ on the splash, or with `--world`:

    snek --world 5

The side panel shows the world's **pace**: the snake's speed on screen, which is the same whatever
the size of the board's cells. So that turns stay responsive, the snake never drops below a minimum
number of moves a second, so a board with big cells (such as Arcade's) runs a little faster on
screen than its pace.

Other flags override single settings of the mode, such as `--no-walls` or `--food glyphs`; run
`snek --help` for them all. Demo strategy choices are `floodfill` (the default), `greedy`,
`safe-bfs`, and `hamiltonian`. Select one before pressing D with, for example:

    snek --demo-strategy hamiltonian

The supported minimum terminal size is **80 columns × 24 rows**. The game model remains safe if
the terminal is made smaller, but interface elements may be clipped.

### Controls

- **Arrow keys** or **WASD**: Move the snake
- **Space**: Start game / Pause/unpause the game / Restart after game over
- **←/→** (on the splash screen): Change the game mode (Classic, Arcade, Arena, Pixel Arena)
- **↑/↓** (on the splash screen): Choose the starting world, like Nokia Snake's level: it sets
  the pace and the points per food, and it stays as you change the mode
- **D** (on the splash screen): Watch the snek play itself in demo mode
- **S** (on the splash screen): Settings — starting world, walls, world change, foods per
  world, starting length, board sizing, grid cap, cell scale, smooth motion, food type,
  palette (each world's colours, or the board drawn like the Nokia LCD) and demo strategy, for
  the rest of the session. A combination that can't work, such as pixel-art food at cell scale
  1, is explained in red, and Enter applies the changes only once it is fixed
- **Enter**: Toggle sidebar visibility
- **Esc**: Back to the main menu (from the game, pause, diagnostics or game over; in settings
  it discards the changes)
- **?**: Open scrollable live diagnostics; press **C** there to copy them
- **Q**: Quit the game
