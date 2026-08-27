"""Reject sensitive local artifacts in built Python distributions."""

from __future__ import annotations

import sys
import tarfile
import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

FORBIDDEN_DIRECTORIES = frozenset({".pytest_cache", "cover", "htmlcov"})
FORBIDDEN_EXACT_FILES = frozenset(
    {
        ".coverage",
        ".env",
        ".envrc",
        "coverage.json",
        "coverage.lcov",
        "coverage.xml",
        "nosetests.xml",
    }
)
FORBIDDEN_FILE_PREFIXES = (".coverage.", ".env.", "snapshot_report")


def forbidden_artifact(member_name: str) -> bool:
    """Return whether an archive member is a forbidden local artifact."""
    parts = PurePosixPath(member_name).parts
    if any(part in FORBIDDEN_DIRECTORIES for part in parts):
        return True
    if not parts:
        return False

    filename = parts[-1]
    return (
        filename in FORBIDDEN_EXACT_FILES
        or filename.endswith(".cover")
        or any(filename.startswith(prefix) for prefix in FORBIDDEN_FILE_PREFIXES)
    )


def archive_members(archive_path: Path) -> list[str]:
    """List members from a wheel or gzipped source distribution."""
    if archive_path.suffix == ".whl":
        with zipfile.ZipFile(archive_path) as archive:
            return archive.namelist()
    if archive_path.name.endswith(".tar.gz"):
        with tarfile.open(archive_path, mode="r:gz") as archive:
            return archive.getnames()
    raise ValueError(f"Unsupported distribution archive: {archive_path}")


def check_distribution_archives(archive_paths: Iterable[Path]) -> None:
    """Require a clean sdist and wheel, raising on forbidden members."""
    archive_paths = list(archive_paths)
    archive_kinds = {
        "sdist" if path.name.endswith(".tar.gz") else "wheel"
        for path in archive_paths
        if path.suffix == ".whl" or path.name.endswith(".tar.gz")
    }
    if archive_kinds != {"sdist", "wheel"}:
        raise ValueError("Expected at least one .tar.gz sdist and one .whl wheel")

    violations = {
        path: [name for name in archive_members(path) if forbidden_artifact(name)]
        for path in archive_paths
    }
    violations = {path: names for path, names in violations.items() if names}
    if violations:
        details = "; ".join(
            f"{path}: {', '.join(names)}" for path, names in violations.items()
        )
        raise ValueError(f"Forbidden distribution artifacts found: {details}")


def main(arguments: list[str] | None = None) -> int:
    """Validate archive paths passed on the command line."""
    arguments = sys.argv[1:] if arguments is None else arguments
    try:
        check_distribution_archives(Path(argument) for argument in arguments)
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Validated {len(arguments)} distribution archives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
