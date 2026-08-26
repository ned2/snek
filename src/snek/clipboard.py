"""Best-effort copy to the system clipboard.

Textual's `App.copy_to_clipboard` uses the terminal OSC 52 escape sequence, which
is widely but not universally honoured: some terminals and multiplexers (e.g.
tmux without `set-clipboard on`) ignore it — or even leak the sequence onto the
screen — so nothing reaches the clipboard. We therefore prefer a local clipboard
utility (`wl-copy`/`xclip`/`xsel`/`pbcopy`/`clip`), which writes straight to the
OS clipboard, and fall back to OSC 52 (the only option over SSH).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
import shutil
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.app import App

# Labels returned by `copy_text` identifying which mechanism was used. OSC 52 is
# the unreliable fallback (callers may want to warn when it's hit).
METHOD_SYSTEM = "system clipboard"
METHOD_OSC52 = "terminal (OSC 52)"
SYSTEM_COPY_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class CopyResult:
    """Outcome of a clipboard attempt, including any OSC 52 fallback reason."""

    method: str
    detail: str | None = None


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


async def _kill_process(process: asyncio.subprocess.Process) -> None:
    """Kill and reap a clipboard subprocess if it is still running."""
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    await process.wait()


def _osc52_fallback(app: App, text: str, detail: str) -> CopyResult:
    """Copy through Textual's terminal fallback and retain the system failure."""
    app.copy_to_clipboard(text)
    return CopyResult(METHOD_OSC52, detail)


async def copy_text(
    app: App,
    text: str,
    *,
    timeout: float = SYSTEM_COPY_TIMEOUT_SECONDS,
) -> CopyResult:
    """Copy `text` without blocking Textual's event loop.

    Tries a local clipboard utility first (most reliable), then OSC 52 via
    Textual so a remote/SSH session can still copy to the *local* machine. A
    timed-out or cancelled utility is killed and reaped before this returns.
    """
    command = _system_clipboard_command()
    if command is None:
        return _osc52_fallback(app, text, "No system clipboard tool found")

    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(process.communicate(text.encode("utf-8")), timeout)
    except TimeoutError:
        if process is not None:
            await _kill_process(process)
        return _osc52_fallback(app, text, "System clipboard command timed out")
    except asyncio.CancelledError:
        if process is not None:
            await _kill_process(process)
        raise
    except OSError:
        if process is not None:
            await _kill_process(process)
        return _osc52_fallback(app, text, "System clipboard command unavailable")

    if process.returncode == 0:
        return CopyResult(METHOD_SYSTEM)

    return _osc52_fallback(
        app,
        text,
        f"System clipboard command exited with status {process.returncode}",
    )
