"""Regression tests for the local quality-gate lifecycle (Makefile and helpers)."""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import check_pushed_ref
from scripts.check_distribution import main as check_distribution_main
from scripts.smoke_installed import check_installed_app

PROJECT_ROOT = Path(__file__).parents[1]
QUALITY_DIR = PROJECT_ROOT / ".quality"

needs_make = pytest.mark.skipif(shutil.which("make") is None, reason="needs GNU Make")


def dry_run(*arguments: str) -> list[str]:
    """Return the commands ``make`` would run, one per logical line."""
    result = subprocess.run(
        [
            "make",
            "--dry-run",
            "--no-print-directory",
            "-C",
            str(PROJECT_ROOT),
            *arguments,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.replace("\\\n", " ").splitlines()


@needs_make
def test_uv_commands_are_locked() -> None:
    commands = dry_run("quality", "pre-push", "install-hooks")
    for command in commands:
        if "uv run" in command:
            assert "uv run --locked" in command or (
                "uv run --isolated --no-project" in command
            ), command
        if "uv export" in command:
            assert "--locked" in command, command


@needs_make
def test_gate_coverage_lives_under_quality_dir() -> None:
    commands = dry_run("test")
    pytest_command = next(command for command in commands if " pytest " in command)
    report_command = next(
        command for command in commands if "coverage report" in command
    )
    coverage_file = f"COVERAGE_FILE={QUALITY_DIR / 'coverage'}"
    assert pytest_command.startswith(coverage_file)
    assert report_command.startswith(coverage_file)
    for flag in ("--quiet", "-n", "--maxprocesses=8", "--cov=src/snek", "--cov-branch"):
        assert flag in shlex.split(pytest_command)
    assert all("erase" not in command for command in commands)


@needs_make
def test_deletions_stay_inside_quality_dir() -> None:
    for target in ("quality", "clean-quality"):
        for command in dry_run(target):
            words = shlex.split(command)
            if words[:1] == ["rm"]:
                assert words[1] == "-rf"
                assert all(path.split("/")[0] == ".quality" for path in words[2:]), (
                    command
                )


@needs_make
def test_quality_runs_every_stage_in_order() -> None:
    commands = dry_run("quality")
    stages = [
        "uv lock --check",
        "ruff check",
        "ruff format --check",
        "ty check",
        " pytest ",
        "coverage report",
        "uv export",
        "pip-audit",
        "uv build",
        "check_distribution.py",
        "snek --help",
        "smoke_installed.py",
    ]
    positions = [
        next(index for index, command in enumerate(commands) if stage in command)
        for stage in stages
    ]
    assert positions == sorted(positions)


@needs_make
def test_parallel_make_runs_the_same_serial_sequence() -> None:
    assert dry_run("-j8", "quality") == dry_run("quality")


def test_deleted_ref_skips_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("A deleted ref must not create a worktree")

    monkeypatch.setattr(check_pushed_ref.subprocess, "run", unexpected_run)
    check_pushed_ref.check_revision("0" * 40)


def _record_runs(
    monkeypatch: pytest.MonkeyPatch, *, fail: str | None = None
) -> list[tuple[list[str], Path, dict[str, str] | None]]:
    calls: list[tuple[list[str], Path, dict[str, str] | None]] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        assert check
        calls.append((command, cwd, env))
        if command[0] == fail:
            raise subprocess.CalledProcessError(2, command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check_pushed_ref.subprocess, "run", fake_run)
    return calls


def test_pre_push_checks_target_in_detached_worktree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record_runs(monkeypatch)
    monkeypatch.setenv(check_pushed_ref.PRE_COMMIT_TO_REF, "target-commit")
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", str(PROJECT_ROOT / ".venv"))
    monkeypatch.setenv("VIRTUAL_ENV", str(PROJECT_ROOT / ".venv"))
    monkeypatch.setenv("MAKEFLAGS", "-j8")

    check_pushed_ref.check_revision("target-commit")

    add_command, add_cwd, _ = calls[0]
    assert add_command[:4] == ["git", "worktree", "add", "--detach"]
    assert add_command[-1] == "target-commit"
    checkout = Path(add_command[-2])
    assert add_cwd == check_pushed_ref.PROJECT_ROOT

    gate_command, gate_cwd, gate_environment = calls[1]
    assert gate_command == ["make", "quality"]
    assert gate_cwd == checkout
    assert gate_environment is not None
    assert gate_environment["UV_PROJECT_ENVIRONMENT"] == str(checkout / ".venv")
    for inherited in (check_pushed_ref.PRE_COMMIT_TO_REF, "VIRTUAL_ENV", "MAKEFLAGS"):
        assert inherited not in gate_environment

    remove_command, remove_cwd, _ = calls[2]
    assert remove_command == ["git", "worktree", "remove", "--force", str(checkout)]
    assert remove_cwd == check_pushed_ref.PROJECT_ROOT


def test_failed_gate_still_removes_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _record_runs(monkeypatch, fail="make")

    with pytest.raises(subprocess.CalledProcessError):
        check_pushed_ref.check_revision("target-commit")

    assert [command[:3] for command, _, _ in calls][-1] == ["git", "worktree", "remove"]


def test_pre_push_defaults_to_head(monkeypatch: pytest.MonkeyPatch) -> None:
    revisions: list[str] = []
    monkeypatch.delenv(check_pushed_ref.PRE_COMMIT_TO_REF, raising=False)
    monkeypatch.setattr(check_pushed_ref, "check_revision", revisions.append)

    assert check_pushed_ref.main() == 0
    assert revisions == ["HEAD"]


@pytest.mark.parametrize(
    "names",
    [
        [],
        ["snek_tui-1.0-py3-none-any.whl"],
        ["snek_tui-1.0.tar.gz"],
        [
            "snek_tui-1.0-py3-none-any.whl",
            "snek_tui-0.9-py3-none-any.whl",
            "snek_tui-1.0.tar.gz",
        ],
    ],
)
def test_distribution_check_requires_one_build(
    tmp_path: Path, names: list[str]
) -> None:
    assert check_distribution_main([str(tmp_path / name) for name in names]) == 1


@pytest.mark.asyncio
async def test_installed_application_probe_loads_current_app() -> None:
    await check_installed_app()
