"""Run the complete quality gate on the exact revision being pushed.

pre-commit's pre-push stage names the pushed commit in ``PRE_COMMIT_TO_REF`` but runs hooks in
the developer's checkout, whose working tree and index may differ from it: a staged fix could
make a broken commit pass. This checks the revision out in a temporary detached worktree and runs
that revision's own ``make quality`` there. Without ``PRE_COMMIT_TO_REF`` it checks ``HEAD``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRE_COMMIT_TO_REF = "PRE_COMMIT_TO_REF"

# Variables tying a process to the developer's checkout or to the calling make. The worktree's
# gate runs without them; ``UV_PROJECT_ENVIRONMENT`` is replaced instead (see below).
_CHECKOUT_VARIABLES = frozenset(
    {PRE_COMMIT_TO_REF, "VIRTUAL_ENV", "MAKEFLAGS", "MFLAGS", "MAKELEVEL"}
)


def is_null_ref(revision: str) -> bool:
    """Return whether Git represents this ref as a deletion."""
    return bool(revision) and set(revision) == {"0"}


def worktree_environment(checkout: Path) -> dict[str, str]:
    """Return the gate's environment for ``checkout``.

    The tracked ``.envrc`` exports an absolute ``UV_PROJECT_ENVIRONMENT`` for the developer's
    checkout, which the hook inherits. Left in place, ``uv run`` in the worktree would sync the
    developer's ``.venv`` against the pushed revision, so it points at the worktree's own.
    """
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in _CHECKOUT_VARIABLES
    }
    environment["UV_PROJECT_ENVIRONMENT"] = str(checkout / ".venv")
    return environment


def check_revision(revision: str) -> None:
    """Run ``make quality`` for ``revision`` in a temporary detached worktree."""
    if is_null_ref(revision):
        print("Skipping quality gates for a deleted ref.")
        return

    with TemporaryDirectory(prefix="snek-pushed-ref-") as temporary_directory:
        checkout = Path(temporary_directory) / "checkout"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(checkout), revision],
            cwd=PROJECT_ROOT,
            check=True,
        )
        try:
            subprocess.run(
                ["make", "quality"],
                cwd=checkout,
                env=worktree_environment(checkout),
                check=True,
            )
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(checkout)],
                cwd=PROJECT_ROOT,
                check=True,
            )


def main() -> int:
    """Check the pushed revision, or ``HEAD`` when run directly."""
    revision = os.environ.get(PRE_COMMIT_TO_REF) or "HEAD"
    try:
        check_revision(revision)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"\nQuality gate failed for {revision}: {error}", file=sys.stderr)
        return 1

    print(f"\nAll local quality gates passed for {revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
