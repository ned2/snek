"""Regression tests for local quality-gate orchestration."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import check_quality
from scripts.smoke_installed import check_installed_app


def test_uv_commands_are_locked() -> None:
    assert check_quality.uv_run("ruff", "check") == [
        "uv",
        "run",
        "--locked",
        "ruff",
        "check",
    ]


def test_deleted_ref_skips_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("A deleted ref must not create a worktree")

    monkeypatch.setattr(check_quality.subprocess, "run", unexpected_run)
    check_quality.run_pushed_revision("0" * 40)


def test_pre_push_checks_target_in_detached_worktree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check_quality.subprocess, "run", fake_run)
    monkeypatch.setenv(check_quality.PRE_COMMIT_TO_REF, "target-commit")

    check_quality.run_pushed_revision("target-commit")

    add_command, add_cwd, _ = calls[0]
    assert add_command[:4] == ["git", "worktree", "add", "--detach"]
    assert add_command[-1] == "target-commit"
    checkout = Path(add_command[-2])
    assert add_cwd == check_quality.PROJECT_ROOT

    child_command, child_cwd, child_environment = calls[1]
    assert child_command == check_quality.uv_run("python", "scripts/check_quality.py")
    assert child_cwd == checkout
    assert child_environment is not None
    assert check_quality.PRE_COMMIT_TO_REF not in child_environment

    remove_command, remove_cwd, _ = calls[2]
    assert remove_command == [
        "git",
        "worktree",
        "remove",
        "--force",
        str(checkout),
    ]
    assert remove_cwd == check_quality.PROJECT_ROOT


def test_gate_uses_disposable_coverage_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, list[str], dict[str, str] | None]] = []

    def fake_gate(
        name: str,
        command: list[str],
        *,
        cwd: Path = check_quality.PROJECT_ROOT,
        env: dict[str, str] | None = None,
    ) -> None:
        assert cwd == check_quality.PROJECT_ROOT
        calls.append((name, command, env))

    monkeypatch.setattr(check_quality, "run_gate", fake_gate)
    monkeypatch.setattr(
        check_quality,
        "built_archives",
        lambda directory: [
            directory / "snek_tui-0.1.1-py3-none-any.whl",
            directory / "snek_tui-0.1.1.tar.gz",
        ],
    )

    check_quality.run_quality_gates()

    coverage_calls = [call for call in calls if call[0].startswith("Coverage")]
    test_call = next(call for call in calls if call[0] == "Tests with branch coverage")
    assert len(coverage_calls) == 1
    assert "--quiet" in test_call[1]
    assert "-n" in test_call[1]
    assert "--maxprocesses=8" in test_call[1]
    assert "--cov=src/snek" in test_call[1]
    assert "--cov-branch" in test_call[1]
    assert test_call[2] is not None
    assert coverage_calls[0][2] is not None
    test_coverage_file = test_call[2]["COVERAGE_FILE"]
    report_coverage_file = coverage_calls[0][2]["COVERAGE_FILE"]
    assert test_coverage_file == report_coverage_file
    assert Path(test_coverage_file).name == "coverage"
    assert Path(test_coverage_file).parent != check_quality.PROJECT_ROOT
    assert all("erase" not in command for _, command, _ in calls)


@pytest.mark.asyncio
async def test_installed_application_probe_loads_current_app() -> None:
    await check_installed_app()
