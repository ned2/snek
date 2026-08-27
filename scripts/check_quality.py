"""Run the complete local quality gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_gate(name: str, command: list[str]) -> None:
    """Run one gate and stop immediately if it fails."""
    print(f"\n==> {name}", flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def built_archives(directory: Path) -> list[Path]:
    """Return the wheel and source archive produced in a build directory."""
    return sorted((*directory.glob("*.whl"), *directory.glob("*.tar.gz")))


def main() -> int:
    """Run every local gate against locked dependencies and temporary artifacts."""
    try:
        run_gate("Lockfile", ["uv", "lock", "--check"])
        run_gate("Ruff lint", ["uv", "run", "ruff", "check", "."])
        run_gate("Ruff format", ["uv", "run", "ruff", "format", "--check", "."])
        run_gate("Type checking", ["uv", "run", "ty", "check"])
        run_gate("Reset coverage", ["uv", "run", "coverage", "erase"])
        run_gate(
            "Tests with branch coverage",
            ["uv", "run", "coverage", "run", "-m", "pytest"],
        )
        run_gate("Coverage floor", ["uv", "run", "coverage", "report"])

        with TemporaryDirectory(prefix="snek-quality-") as temporary_directory:
            workspace = Path(temporary_directory)
            requirements = workspace / "runtime-requirements.txt"
            distributions = workspace / "dist"

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
                [
                    "uv",
                    "run",
                    "pip-audit",
                    "--disable-pip",
                    "--requirement",
                    str(requirements),
                ],
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
                raise RuntimeError(
                    "Expected exactly one wheel and one source distribution"
                )

            run_gate(
                "Wheel install and CLI smoke test",
                [
                    "uv",
                    "run",
                    "--isolated",
                    "--no-project",
                    "--with",
                    str(wheels[0]),
                    "snek",
                    "--help",
                ],
            )
            run_gate(
                "Source install and CLI smoke test",
                [
                    "uv",
                    "run",
                    "--isolated",
                    "--no-project",
                    "--with",
                    str(source_distributions[0]),
                    "snek",
                    "--help",
                ],
            )
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"\nQuality gate failed: {error}", file=sys.stderr)
        return 1

    print("\nAll local quality gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
