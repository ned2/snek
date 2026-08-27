"""Regression tests for deterministic pytest discovery and visual snapshots."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from snek.app import SnakeApp

PROJECT_ROOT = Path(__file__).parents[1]


def test_effective_pytest_configuration(pytestconfig: pytest.Config) -> None:
    """The intended root, discovery, asyncio, and report settings are active."""
    assert pytestconfig.rootpath == PROJECT_ROOT
    assert pytestconfig.inipath == PROJECT_ROOT / "pytest.ini"
    assert pytestconfig.getini("testpaths") == ["tests"]
    assert pytestconfig.getini("python_files") == ["test_*.py"]
    assert pytestconfig.getini("python_classes") == ["Test*"]
    assert pytestconfig.getini("python_functions") == ["test_*"]
    assert pytestconfig.getini("asyncio_mode") == "auto"
    assert pytestconfig.getini("asyncio_default_fixture_loop_scope") == "function"
    assert pytestconfig.getini("asyncio_default_test_loop_scope") == "function"
    assert pytestconfig.getini("addopts") == [
        "-v",
        "--tb=short",
        "--snapshot-report=.pytest_cache/snapshot-report/report.html",
    ]
    assert (
        pytestconfig.getoption("--snapshot-report")
        == ".pytest_cache/snapshot-report/report.html"
    )


def _collect_nodeids(cwd: Path, target: Path | str) -> set[str]:
    """Collect test node IDs from a given working directory."""
    environment = dict(os.environ)
    environment.pop("FORCE_COLOR", None)
    environment.pop("PYTEST_ADDOPTS", None)
    environment["NO_COLOR"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-qq",
            str(target),
        ],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return {line for line in result.stdout.splitlines() if "::" in line}


def test_parent_directory_collects_the_same_tests() -> None:
    """Targeting the repo from its parent retains its config and node IDs."""
    from_root = _collect_nodeids(PROJECT_ROOT, "tests")
    from_parent = _collect_nodeids(PROJECT_ROOT.parent, PROJECT_ROOT / "tests")

    assert from_root
    assert from_parent == from_root


def test_snapshots_ignore_ambient_color_and_terminal_environment() -> None:
    """A hostile caller environment cannot change checked-in visual baselines."""
    environment = dict(os.environ)
    environment.pop("PYTEST_ADDOPTS", None)
    environment.update(
        {
            "NO_COLOR": "1",
            "FORCE_COLOR": "1",
            "TERM": "unknown-terminal",
            "COLORTERM": "monochrome",
        }
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_snapshots.py"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout


def test_explicit_no_color_mode_remains_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Snapshot normalization does not disable Snek's supported monochrome mode."""
    monkeypatch.setenv("NO_COLOR", "1")

    app = SnakeApp()

    assert app.no_color
    assert "nocolor" in app.pseudo_classes
