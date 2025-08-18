"""Valid colors for Rich/Textual framework."""

# Standard ANSI colors that work in both Rich and Textual
VALID_COLORS = {
    "black": "black",
    "red": "red",
    "green": "green",
    "yellow": "yellow",
    "blue": "blue",
    "magenta": "magenta",  # Use instead of "purple"
    "cyan": "cyan",
    "white": "white",
}

# Extended color options using RGB
EXTENDED_COLORS = {
    "orange": "rgb(255,165,0)",
    "purple": "rgb(128,0,128)",
    "pink": "rgb(255,192,203)",
    "brown": "rgb(165,42,42)",
    "gray": "rgb(128,128,128)",
}

# Color aliases for better naming
COLOR_ALIASES = {
    "purple": "magenta",  # Rich uses 'magenta' for purple
    "grey": "gray",
}


def get_valid_color(color_name: str) -> str:
    """Get a valid color string for Rich/Textual.

    Args:
        color_name: The desired color name

    Returns:
        A valid color string that Rich/Textual can use
    """
    # Check if it's already valid
    if color_name in VALID_COLORS:
        return VALID_COLORS[color_name]

    # Check aliases
    if color_name in COLOR_ALIASES:
        return COLOR_ALIASES[color_name]

    # Check extended colors
    if color_name in EXTENDED_COLORS:
        return EXTENDED_COLORS[color_name]

    # Default to the input (might be RGB or hex)
    return color_name
