"""Regression tests for snapshot reports and distribution contents."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.check_distribution import (
    check_distribution_archives,
    forbidden_artifact,
)
from tests.snapshot_safety import sanitized_snapshot_environment

PROJECT_ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    "member_name",
    [
        "package/.pytest_cache/v/cache/nodeids",
        "package/htmlcov/index.html",
        "package/snapshot_report.html",
        "package/snapshot_report-failure.html",
        "package/.env",
        "package/.env.local",
        "package/.envrc",
        "package/.coverage",
        "package/.coverage.worker",
        "package/cover/index.html",
        "package/coverage.json",
        "package/coverage.lcov",
        "package/coverage.xml",
        "package/nosetests.xml",
        "package/test.cover",
        "package/test.py.cover",
    ],
)
def test_forbidden_artifact_recognizes_sensitive_paths(member_name: str) -> None:
    assert forbidden_artifact(member_name)


def test_snapshot_environment_is_allowlisted_and_restored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = 'snek-secret-"><script>alert(1)</script>'
    monkeypatch.setenv("SNEK_SECRET_SENTINEL", sentinel)
    monkeypatch.setenv("TEXTUAL_SNAPSHOT_TEMPDIR", sentinel)
    original_environment = os.environ

    with sanitized_snapshot_environment():
        assert os.environ["TEXTUAL_SNAPSHOT_TEMPDIR"] == sentinel
        assert dict(os.environ) == {}
        os.environ.update({"NO_COLOR": "1"})
        assert os.environ["NO_COLOR"] == "1"
        os.environ.clear()
        assert os.environ["TEXTUAL_SNAPSHOT_TEMPDIR"] == sentinel
        assert dict(os.environ) == {}

    assert os.environ is original_environment


def test_failing_snapshot_report_excludes_ambient_secrets(tmp_path: Path) -> None:
    probe_root = tmp_path / "snapshot-probe"
    probe_files = [
        "pytest.ini",
        "tests/__init__.py",
        "tests/conftest.py",
        "tests/snapshot_safety.py",
        "tests/fixtures/snapshot_failure_probe.py",
    ]
    for relative_path in probe_files:
        destination = probe_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT_ROOT / relative_path, destination)

    report_path = probe_root / ".pytest_cache" / "snapshot-report" / "report.html"
    sentinel = 'snek-secret-"><script>alert(1)</script>'
    environment = dict(os.environ)
    environment.pop("PYTEST_XDIST_WORKER", None)
    environment.pop("TEXTUAL_SNAPSHOT_TEMPDIR", None)
    environment["SNEK_SECRET_SENTINEL"] = sentinel

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/fixtures/snapshot_failure_probe.py",
            "-q",
        ],
        cwd=probe_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "SNEK_SECRET_SENTINEL" not in report
    assert "TEXTUAL_SNAPSHOT_TEMPDIR" not in report
    assert sentinel not in report
    assert not (probe_root / "snapshot_report.html").exists()


def _write_sdist(path: Path, member_names: list[str]) -> None:
    with tarfile.open(path, mode="w:gz") as archive:
        for member_name in member_names:
            content = b"test artifact"
            member = tarfile.TarInfo(member_name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))


def _write_wheel(path: Path, member_names: list[str]) -> None:
    with zipfile.ZipFile(path, mode="w") as archive:
        for member_name in member_names:
            archive.writestr(member_name, "test artifact")


def test_distribution_checker_opens_sdist_and_wheel(tmp_path: Path) -> None:
    sdist_path = tmp_path / "snek_tui-0.1.1.tar.gz"
    wheel_path = tmp_path / "snek_tui-0.1.1-py3-none-any.whl"
    _write_sdist(sdist_path, ["snek_tui-0.1.1/src/snek/app.py"])
    _write_wheel(wheel_path, ["snek/app.py"])

    check_distribution_archives([sdist_path, wheel_path])

    _write_sdist(sdist_path, ["snek_tui-0.1.1/snapshot_report.html"])
    with pytest.raises(ValueError, match=r"snapshot_report\.html"):
        check_distribution_archives([sdist_path, wheel_path])


def test_hatch_build_excludes_local_artifacts(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    shutil.copytree(
        PROJECT_ROOT,
        project_path,
        ignore=shutil.ignore_patterns(
            ".git",
            ".pytest_cache",
            ".venv",
            "__pycache__",
            "dist",
            "htmlcov",
        ),
    )
    (project_path / ".gitignore").unlink()

    decoy_paths = [
        "snapshot_report.html",
        ".env.local",
        ".envrc",
        ".coverage.worker",
        "coverage.json",
        "coverage.lcov",
        "coverage.xml",
        "cover/index.html",
        "htmlcov/index.html",
        "nosetests.xml",
        "test.cover",
        "src/snek/.pytest_cache/cache",
        "src/snek/snapshot_report-nested.html",
        "src/snek/.env.nested",
    ]
    for relative_path in decoy_paths:
        decoy_path = project_path / relative_path
        decoy_path.parent.mkdir(parents=True, exist_ok=True)
        decoy_path.write_text("issue-0006 exclusion probe", encoding="utf-8")

    output_path = tmp_path / "dist"
    result = subprocess.run(
        [sys.executable, "-m", "hatchling", "build", "-d", str(output_path)],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    archives = [*output_path.glob("*.tar.gz"), *output_path.glob("*.whl")]
    check_distribution_archives(archives)
