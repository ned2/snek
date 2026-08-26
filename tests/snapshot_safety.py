"""Safety helpers for pytest-textual-snapshot failure reports."""

import os
from collections.abc import Iterator, MutableMapping
from contextlib import contextmanager


SNAPSHOT_OPERATIONAL_ENVIRONMENT = frozenset(
    {
        "PYTEST_XDIST_WORKER",
        "TEXTUAL_SNAPSHOT_TEMPDIR",
    }
)


class _NonReportingEnvironment(MutableMapping[str, str]):
    """Provide operational lookups while serializing as an empty mapping.

    pytest-textual-snapshot requires two environment lookups to coordinate its
    temporary files, then renders ``dict(os.environ)`` without HTML escaping.
    Hiding iteration keeps even those operational values out of the report.
    """

    def __init__(self, operational_environment: dict[str, str]) -> None:
        self._operational_environment = operational_environment
        self._transient_environment: dict[str, str] = {}

    def __getitem__(self, key: str) -> str:
        try:
            return self._transient_environment[key]
        except KeyError:
            return self._operational_environment[key]

    def __setitem__(self, key: str, value: str) -> None:
        self._transient_environment[key] = value

    def __delitem__(self, key: str) -> None:
        try:
            del self._transient_environment[key]
        except KeyError:
            del self._operational_environment[key]

    def __iter__(self) -> Iterator[str]:
        return iter(())

    def __len__(self) -> int:
        return 0

    def clear(self) -> None:
        """Clear hook-local updates without removing operational lookups."""
        self._transient_environment.clear()


@contextmanager
def sanitized_snapshot_environment() -> Iterator[None]:
    """Hide all values while preserving the plugin's operational lookups."""
    original_environment = os.environ
    operational_environment = {
        name: original_environment[name]
        for name in SNAPSHOT_OPERATIONAL_ENVIRONMENT
        if name in original_environment
    }

    try:
        os.environ = _NonReportingEnvironment(operational_environment)
        yield
    finally:
        os.environ = original_environment
