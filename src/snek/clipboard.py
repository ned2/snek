"""Best-effort copy to the system clipboard.

Textual's `App.copy_to_clipboard` uses the terminal OSC 52 escape sequence, which
is widely but not universally honoured: some terminals and multiplexers (e.g.
tmux without `set-clipboard on`) ignore it — or even leak the sequence onto the
screen — so nothing reaches the clipboard. We therefore prefer a local clipboard
utility (`wl-copy`/`xclip`/`xsel`/`pbcopy`/`clip`), which writes straight to the
OS clipboard, and fall back to OSC 52 (the only option over SSH).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.app import App

# Labels returned by `copy_text` identifying which mechanism was used. OSC 52 is
# the unreliable fallback (callers may want to warn when it's hit).
METHOD_SYSTEM = "system clipboard"
METHOD_OSC52 = "terminal (OSC 52)"


def _system_clipboard_command() -> list[str] | None:
    """The available local clipboard command for this platform, or None."""
    if sys.platform == "darwin":
        return ["pbcopy"] if shutil.which("pbcopy") else None
    if sys.platform == "win32":
        return ["clip"] if shutil.which("clip") else None
    # Linux / other unix: prefer Wayland when present, then fall back to X11.
    candidates: list[list[str]] = []
    if os.environ.get("WAYLAND_DISPLAY"):
        candidates.append(["wl-copy"])
    candidates += [
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
        ["wl-copy"],
    ]
    for command in candidates:
        if shutil.which(command[0]):
            return command
    return None


def copy_text(app: App, text: str) -> str:
    """Copy `text` to the clipboard; return a short label of the method used.

    Tries a local clipboard utility first (most reliable), then OSC 52 via
    Textual so a remote/SSH session can still copy to the *local* machine.
    """
    command = _system_clipboard_command()
    if command is not None:
        try:
            subprocess.run(command, input=text.encode("utf-8"), check=True, timeout=5)
            return METHOD_SYSTEM
        except (OSError, subprocess.SubprocessError):
            pass  # fall through to OSC 52
    app.copy_to_clipboard(text)
    return METHOD_OSC52
