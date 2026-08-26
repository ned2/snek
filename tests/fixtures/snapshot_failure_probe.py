"""Deliberately failing snapshot used by the report-security regression test."""

from collections.abc import Callable

from textual.app import App


def test_intentional_snapshot_failure(
    snap_compare: Callable[..., bool],
) -> None:
    """Produce a report without relying on a checked-in snapshot baseline."""
    assert snap_compare(App(), terminal_size=(20, 5))
