"""Theme definitions for the Snek game."""

from typing import Final

from textual.theme import Theme

# The Nokia LCD screen's two tones: dark pixels on a green-grey backlight.
LCD_LIGHT: Final = "#c7f0d8"
LCD_DARK: Final = "#43523d"

# The theme for the "lcd" palette, whatever the world.
LCD_THEME: Final = "snek-lcd"

THEME_MAP = {
    "snek-classic": Theme(
        name="snek-classic",
        primary="#00ff00",  # Bright green
        secondary="#00cc00",
        accent="#ffff00",
        foreground="#ffffff",
        background="#000000",
        success="#00ff00",
        warning="#ffff00",
        error="#ff0000",
        surface="#1a1a1a",
        panel="#2a2a2a",
        dark=True,
    ),
    "snek-ocean": Theme(
        name="snek-ocean",
        primary="#00ffff",  # Cyan
        secondary="#0099cc",
        accent="#00ff99",
        foreground="#e0f7fa",
        background="#001f3f",
        success="#00ff99",
        warning="#ffcc00",
        error="#ff6b6b",
        surface="#003366",
        panel="#004080",
        dark=True,
    ),
    "snek-sunset": Theme(
        name="snek-sunset",
        primary="#ffff00",  # Yellow
        secondary="#ff9900",
        accent="#ff6600",
        foreground="#fff8dc",
        background="#1a0f00",
        success="#90ee90",
        warning="#ffa500",
        error="#ff4500",
        surface="#2a1f00",
        panel="#3a2f00",
        dark=True,
    ),
    "snek-royal": Theme(
        name="snek-royal",
        primary="#ff00ff",  # Magenta
        secondary="#cc00cc",
        accent="#ff66ff",
        foreground="#ffe0ff",
        background="#1a001a",
        success="#90ee90",
        warning="#ffcc00",
        error="#ff6666",
        surface="#330033",
        panel="#4d004d",
        dark=True,
    ),
    "snek-cherry": Theme(
        name="snek-cherry",
        primary="#ff0000",  # Red
        secondary="#cc0000",
        accent="#ff6666",
        foreground="#ffe0e0",
        background="#1a0000",
        success="#90ee90",
        warning="#ffcc00",
        error="#ff0000",
        surface="#330000",
        panel="#4d0000",
        dark=True,
    ),
    # Two-tone throughout, error text included: every colour is a dark pixel
    # except the backgrounds. The panel colour is dark too, so titles that
    # shade from primary to panel stay solid.
    LCD_THEME: Theme(
        name=LCD_THEME,
        primary=LCD_DARK,
        secondary=LCD_DARK,
        accent=LCD_DARK,
        foreground=LCD_DARK,
        background=LCD_LIGHT,
        success=LCD_DARK,
        warning=LCD_DARK,
        error=LCD_DARK,
        surface=LCD_LIGHT,
        panel=LCD_DARK,
        dark=False,
    ),
}
