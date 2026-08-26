"""Tests for the best-effort clipboard helper."""

import asyncio

import pytest

from snek import clipboard


class _FakeApp:
    """Minimal stand-in capturing the OSC 52 fallback."""

    def __init__(self) -> None:
        self.osc52_text: str | None = None

    def copy_to_clipboard(self, text: str) -> None:
        self.osc52_text = text


class _FakeProcess:
    """Controllable asyncio subprocess stand-in."""

    def __init__(
        self,
        returncode: int = 0,
        communicate_error: BaseException | None = None,
    ) -> None:
        self.returncode: int | None = None
        self._final_returncode = returncode
        self._communicate_error = communicate_error
        self.input: bytes | None = None
        self.killed = False
        self.waited = False

    async def communicate(self, input: bytes) -> tuple[bytes, bytes]:  # noqa: A002
        self.input = input
        if self._communicate_error is not None:
            raise self._communicate_error
        self.returncode = self._final_returncode
        return b"", b""

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        self.waited = True
        assert self.returncode is not None
        return self.returncode


async def _return_process(
    process: _FakeProcess, *_args: object, **_kwargs: object
) -> _FakeProcess:
    """Return a configured fake from a create_subprocess_exec replacement."""
    return process


class TestSystemClipboardCommand:
    def test_macos_uses_pbcopy(self, monkeypatch):
        monkeypatch.setattr(clipboard.sys, "platform", "darwin")
        monkeypatch.setattr(clipboard.shutil, "which", lambda name: f"/usr/bin/{name}")
        assert clipboard._system_clipboard_command() == ["pbcopy"]

    def test_windows_uses_clip(self, monkeypatch):
        monkeypatch.setattr(clipboard.sys, "platform", "win32")
        monkeypatch.setattr(clipboard.shutil, "which", lambda name: f"C:\\{name}.exe")
        assert clipboard._system_clipboard_command() == ["clip"]

    def test_linux_prefers_wayland(self, monkeypatch):
        monkeypatch.setattr(clipboard.sys, "platform", "linux")
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        monkeypatch.setattr(clipboard.shutil, "which", lambda name: "/usr/bin/wl-copy")
        assert clipboard._system_clipboard_command() == ["wl-copy"]

    def test_linux_falls_back_to_xclip(self, monkeypatch):
        monkeypatch.setattr(clipboard.sys, "platform", "linux")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.setattr(
            clipboard.shutil,
            "which",
            lambda name: "/usr/bin/xclip" if name == "xclip" else None,
        )
        assert clipboard._system_clipboard_command() == [
            "xclip",
            "-selection",
            "clipboard",
        ]

    def test_linux_falls_through_xsel_then_wl_copy(self, monkeypatch):
        monkeypatch.setattr(clipboard.sys, "platform", "linux")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        available = {"xsel"}
        monkeypatch.setattr(
            clipboard.shutil,
            "which",
            lambda name: f"/usr/bin/{name}" if name in available else None,
        )
        assert clipboard._system_clipboard_command() == [
            "xsel",
            "--clipboard",
            "--input",
        ]

        available = {"wl-copy"}
        assert clipboard._system_clipboard_command() == ["wl-copy"]

    def test_none_when_no_tool(self, monkeypatch):
        monkeypatch.setattr(clipboard.sys, "platform", "linux")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.setattr(clipboard.shutil, "which", lambda name: None)
        assert clipboard._system_clipboard_command() is None


class TestCopyText:
    @pytest.mark.asyncio
    async def test_uses_system_tool_when_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        process = _FakeProcess()
        monkeypatch.setattr(clipboard, "_system_clipboard_command", lambda: ["wl-copy"])
        monkeypatch.setattr(
            clipboard.asyncio,
            "create_subprocess_exec",
            lambda *args, **kwargs: _return_process(process, *args, **kwargs),
        )
        app = _FakeApp()

        result = await clipboard.copy_text(app, "hello")

        assert result == clipboard.CopyResult(clipboard.METHOD_SYSTEM)
        assert process.input == b"hello"
        assert app.osc52_text is None  # OSC 52 not used when the tool works

    @pytest.mark.asyncio
    async def test_falls_back_to_osc52_when_no_tool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(clipboard, "_system_clipboard_command", lambda: None)
        app = _FakeApp()

        result = await clipboard.copy_text(app, "hello")

        assert result == clipboard.CopyResult(
            clipboard.METHOD_OSC52, "No system clipboard tool found"
        )
        assert app.osc52_text == "hello"

    @pytest.mark.asyncio
    async def test_falls_back_when_tool_cannot_launch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("no such tool")

        monkeypatch.setattr(clipboard, "_system_clipboard_command", lambda: ["wl-copy"])
        monkeypatch.setattr(clipboard.asyncio, "create_subprocess_exec", boom)
        app = _FakeApp()

        result = await clipboard.copy_text(app, "hello")

        assert result == clipboard.CopyResult(
            clipboard.METHOD_OSC52, "System clipboard command unavailable"
        )
        assert app.osc52_text == "hello"

    @pytest.mark.asyncio
    async def test_timeout_kills_process_and_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        process = _FakeProcess(communicate_error=TimeoutError())
        monkeypatch.setattr(clipboard, "_system_clipboard_command", lambda: ["wl-copy"])
        monkeypatch.setattr(
            clipboard.asyncio,
            "create_subprocess_exec",
            lambda *args, **kwargs: _return_process(process, *args, **kwargs),
        )
        app = _FakeApp()

        result = await clipboard.copy_text(app, "hello")

        assert result == clipboard.CopyResult(
            clipboard.METHOD_OSC52, "System clipboard command timed out"
        )
        assert process.killed and process.waited
        assert app.osc52_text == "hello"

    @pytest.mark.asyncio
    async def test_nonzero_exit_falls_back_with_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        process = _FakeProcess(returncode=3)
        monkeypatch.setattr(clipboard, "_system_clipboard_command", lambda: ["wl-copy"])
        monkeypatch.setattr(
            clipboard.asyncio,
            "create_subprocess_exec",
            lambda *args, **kwargs: _return_process(process, *args, **kwargs),
        )
        app = _FakeApp()

        result = await clipboard.copy_text(app, "hello")

        assert result == clipboard.CopyResult(
            clipboard.METHOD_OSC52,
            "System clipboard command exited with status 3",
        )
        assert app.osc52_text == "hello"

    @pytest.mark.asyncio
    async def test_cancellation_kills_and_reaps_process(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        started = asyncio.Event()

        class SlowProcess(_FakeProcess):
            async def communicate(self, input: bytes) -> tuple[bytes, bytes]:  # noqa: A002
                self.input = input
                started.set()
                await asyncio.Event().wait()
                raise AssertionError("unreachable")

        process = SlowProcess()
        monkeypatch.setattr(clipboard, "_system_clipboard_command", lambda: ["wl-copy"])
        monkeypatch.setattr(
            clipboard.asyncio,
            "create_subprocess_exec",
            lambda *args, **kwargs: _return_process(process, *args, **kwargs),
        )
        app = _FakeApp()
        task = asyncio.create_task(clipboard.copy_text(app, "hello"))
        await started.wait()

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
        assert process.killed and process.waited
        assert app.osc52_text is None
