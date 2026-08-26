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
