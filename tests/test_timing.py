"""Tests for the framework-free fixed-step game clock."""

import pytest

from snek.timing import StepClock


def _steps(clock: StepClock, elapsed: float, interval: float) -> int:
    """Run one frame and count the steps it takes."""
    clock.advance(elapsed)
    count = 0
    while clock.take_step(interval):
        count += 1
    return count


def test_no_step_until_a_full_interval_has_accumulated() -> None:
    clock = StepClock()
    assert _steps(clock, 0.05, 0.1) == 0
    assert _steps(clock, 0.05, 0.1) == 1
    assert clock.accumulated == pytest.approx(0.0)


def test_remainder_carries_so_the_average_rate_is_exact() -> None:
    """Frames that don't divide the interval still yield the exact step rate."""
    clock = StepClock()
    total = sum(_steps(clock, 1 / 60, 0.1) for _ in range(600))  # ten seconds
    # Summing 600 float sixtieths can land a hair under 10 s.
    assert total == pytest.approx(100, abs=1)


def test_short_intervals_take_several_steps_per_frame() -> None:
    clock = StepClock()
    total = sum(_steps(clock, 1 / 60, 0.002) for _ in range(60))  # one second
    assert total == pytest.approx(500, abs=1)


def test_interval_is_reread_between_steps() -> None:
    """A speed-up mid-frame applies to the very next step."""
    clock = StepClock()
    clock.advance(0.2)
    assert clock.take_step(0.1)
    # The model sped up after that step: the remaining 0.1 s now holds two steps.
    assert clock.take_step(0.05)
    assert clock.take_step(0.05)
    assert not clock.take_step(0.05)


def test_step_cap_drops_the_backlog() -> None:
    clock = StepClock(max_steps_per_frame=3, max_elapsed=10.0)
    assert _steps(clock, 1.0, 0.1) == 3
    # The backlog is dropped to one interval, not replayed on later frames.
    assert clock.accumulated == pytest.approx(0.1)
    assert _steps(clock, 0.0, 0.1) == 1
    assert _steps(clock, 0.0, 0.1) == 0


def test_long_frames_are_clamped() -> None:
    """A stalled loop (or a suspended terminal) can't schedule a burst."""
    clock = StepClock(max_elapsed=0.25)
    assert _steps(clock, 30.0, 0.1) == 2
    assert clock.accumulated == pytest.approx(0.05)


def test_negative_elapsed_is_ignored() -> None:
    clock = StepClock()
    clock.advance(-1.0)
    assert clock.accumulated == pytest.approx(0.0)


def test_reset_forgets_accumulated_time() -> None:
    clock = StepClock()
    clock.advance(0.09)
    clock.reset()
    assert _steps(clock, 0.02, 0.1) == 0


def test_progress_is_the_fraction_of_the_next_step() -> None:
    clock = StepClock()
    assert clock.progress(0.1) == pytest.approx(0.0)
    clock.advance(0.025)
    assert clock.progress(0.1) == pytest.approx(0.25)
    clock.advance(0.5)
    assert clock.progress(0.1) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_steps_per_frame": 0}, "max_steps_per_frame"),
        ({"max_elapsed": 0.0}, "max_elapsed"),
    ],
)
def test_rejects_invalid_limits(kwargs: dict[str, float], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        StepClock(**kwargs)  # type: ignore[arg-type]
