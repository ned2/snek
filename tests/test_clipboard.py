"""Tests for the best-effort clipboard helper."""

from snek import clipboard


class _FakeApp:
    """Minimal stand-in capturing the OSC 52 fallback."""

    def __init__(self) -> None:
        self.osc52_text: str | None = None

    def copy_to_clipboard(self, text: str) -> None:
        self.osc52_text = text


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

    def test_none_when_no_tool(self, monkeypatch):
        monkeypatch.setattr(clipboard.sys, "platform", "linux")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.setattr(clipboard.shutil, "which", lambda name: None)
        assert clipboard._system_clipboard_command() is None


class TestCopyText:
    def test_uses_system_tool_when_available(self, monkeypatch):
        recorded = {}

        def fake_run(command, input, check, timeout):  # noqa: A002 - mirror subprocess
            recorded["command"] = command
            recorded["input"] = input

        monkeypatch.setattr(clipboard, "_system_clipboard_command", lambda: ["wl-copy"])
        monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
        app = _FakeApp()

        assert clipboard.copy_text(app, "hello") == "system clipboard"
        assert recorded["command"] == ["wl-copy"]
        assert recorded["input"] == b"hello"
        assert app.osc52_text is None  # OSC 52 not used when the tool works

    def test_falls_back_to_osc52_when_no_tool(self, monkeypatch):
        monkeypatch.setattr(clipboard, "_system_clipboard_command", lambda: None)
        app = _FakeApp()
        assert clipboard.copy_text(app, "hello") == "terminal (OSC 52)"
        assert app.osc52_text == "hello"

    def test_falls_back_to_osc52_when_tool_fails(self, monkeypatch):
        def boom(*args, **kwargs):
            raise OSError("no such tool")

        monkeypatch.setattr(clipboard, "_system_clipboard_command", lambda: ["wl-copy"])
        monkeypatch.setattr(clipboard.subprocess, "run", boom)
        app = _FakeApp()
        assert clipboard.copy_text(app, "hello") == "terminal (OSC 52)"
        assert app.osc52_text == "hello"
