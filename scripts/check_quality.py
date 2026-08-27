"""Run the complete local quality gate."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRE_COMMIT_TO_REF = "PRE_COMMIT_TO_REF"


def run_gate(
    name: str,
    command: list[str],
    *,
    cwd: Path = PROJECT_ROOT,
    env: Mapping[str, str] | None = None,
) -> None:
    """Run one gate and stop immediately if it fails."""
    print(f"\n==> {name}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def built_archives(directory: Path) -> list[Path]:
    """Return the wheel and source archive produced in a build directory."""
    return sorted((*directory.glob("*.whl"), *directory.glob("*.tar.gz")))


def uv_run(*arguments: str) -> list[str]:
    """Build a locked command in the project environment."""
    return ["uv", "run", "--locked", *arguments]


def is_null_ref(revision: str) -> bool:
    """Return whether Git represents this ref as a deletion."""
    return bool(revision) and set(revision) == {"0"}


def run_pushed_revision(revision: str) -> None:
    """Run the pushed revision's own quality gate in a detached worktree."""
    if is_null_ref(revision):
        print("Skipping quality gates for a deleted ref.")
        return

    with TemporaryDirectory(prefix="snek-pushed-ref-") as temporary_directory:
        checkout = Path(temporary_directory) / "checkout"
        worktree_added = False
        try:
            run_gate(
                "Checkout pushed revision",
                [
                    "git",
                    "worktree",
                    "add",
                    "--detach",
                    str(checkout),
                    revision,
                ],
            )
            worktree_added = True
            child_environment = dict(os.environ)
            child_environment.pop(PRE_COMMIT_TO_REF, None)
            run_gate(
                "Quality gates for pushed revision",
                uv_run("python", "scripts/check_quality.py"),
                cwd=checkout,
                env=child_environment,
            )
        finally:
            if worktree_added:
                run_gate(
                    "Remove pushed revision worktree",
                    ["git", "worktree", "remove", "--force", str(checkout)],
                )


def run_quality_gates() -> None:
    """Run every local gate against locked dependencies and temporary artifacts."""
    run_gate("Lockfile", ["uv", "lock", "--check"])
    run_gate("Ruff lint", uv_run("ruff", "check", "."))
    run_gate("Ruff format", uv_run("ruff", "format", "--check", "."))
    run_gate("Type checking", uv_run("ty", "check"))

    with TemporaryDirectory(prefix="snek-quality-") as temporary_directory:
        workspace = Path(temporary_directory)
        requirements = workspace / "runtime-requirements.txt"
        distributions = workspace / "dist"
        coverage_environment = dict(os.environ)
        coverage_environment["COVERAGE_FILE"] = str(workspace / "coverage")

        run_gate(
            "Tests with branch coverage",
            uv_run("coverage", "run", "-m", "pytest"),
            env=coverage_environment,
        )
        run_gate(
            "Coverage floor",
            uv_run("coverage", "report"),
            env=coverage_environment,
        )

        run_gate(
            "Export locked runtime dependencies",
            [
                "uv",
                "export",
                "--quiet",
                "--locked",
                "--no-dev",
                "--no-emit-project",
                "--output-file",
                str(requirements),
            ],
        )
        run_gate(
            "Dependency audit",
            uv_run(
                "pip-audit",
                "--disable-pip",
                "--requirement",
                str(requirements),
            ),
        )
        run_gate(
            "Build distributions", ["uv", "build", "--out-dir", str(distributions)]
        )

        archives = built_archives(distributions)
        run_gate(
            "Distribution contents",
            [sys.executable, "scripts/check_distribution.py", *map(str, archives)],
        )

        wheels = [archive for archive in archives if archive.suffix == ".whl"]
        source_distributions = [
            archive for archive in archives if archive.name.endswith(".tar.gz")
        ]
        if len(wheels) != 1 or len(source_distributions) != 1:
            raise RuntimeError("Expected exactly one wheel and one source distribution")

        for name, archive in (
            ("Wheel", wheels[0]),
            ("Source", source_distributions[0]),
        ):
            isolated_environment = [
                "uv",
                "run",
                "--isolated",
                "--no-project",
                "--with",
                str(archive),
            ]
            run_gate(
                f"{name} install and CLI smoke test",
                [*isolated_environment, "snek", "--help"],
            )
            run_gate(
                f"{name} installed application smoke test",
                [*isolated_environment, "python", "scripts/smoke_installed.py"],
            )


def main() -> int:
    """Run the current tree directly, or the exact revision from pre-push."""
    pushed_revision = os.environ.get(PRE_COMMIT_TO_REF)
    try:
        if pushed_revision:
            run_pushed_revision(pushed_revision)
        else:
            run_quality_gates()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"\nQuality gate failed: {error}", file=sys.stderr)
        return 1

    print("\nAll local quality gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
