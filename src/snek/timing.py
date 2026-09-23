"""Fixed-step game clock: decouples the model's step rate from the frame rate.

The game screen runs one steady frame timer and feeds each frame's elapsed wall
time into a `StepClock`, which says how many model steps are due. This is the
accumulator loop from "Fix Your Timestep"
(https://gafferongames.com/post/fix_your_timestep/):

- The step interval is re-read on every step, so a speed-up after eating takes
  effect immediately with no timer restart and no phase reset.
- Paused time is never accumulated: the screen stops feeding frames while paused.
- A stalled frame cannot trigger a burst of catch-up steps. Elapsed time is
  clamped per frame, and steps per frame are capped, with any backlog dropped.

`progress()` exposes how far the clock is into the next step, which is what a
renderer needs to interpolate motion between steps.

`next_wake_delay()` says when the loop should next wake: exactly at the next
step's deadline, or once per frame when steps are shorter than a frame. Waking at
the deadline rather than on a fixed frame grid keeps the step rhythm even when
the interval is not a whole number of frames. An interpolating renderer splits
each step into equal substeps, and the loop wakes at each substep boundary
instead, so every visible increment is evenly spaced too.

Framework-free (no Textual) so it can be unit-tested with plain numbers.
"""

import math


class StepClock:
    """Accumulates elapsed time and hands out fixed-interval model steps.

    Args:
        max_steps_per_frame: The most steps one frame may take. Must allow the
            fastest configured step rate (e.g. 2 ms steps need about 9 per 60 Hz
            frame); a backlog beyond it is dropped rather than carried.
        max_elapsed: Frame times longer than this (a stalled event loop, a
            suspended terminal) are clamped, so they cannot schedule a burst.
    """

    def __init__(
        self,
        max_steps_per_frame: int = 16,
        max_elapsed: float = 0.25,
    ) -> None:
        if max_steps_per_frame < 1:
            raise ValueError("max_steps_per_frame must be at least one")
        if max_elapsed <= 0:
            raise ValueError("max_elapsed must be positive")
        self.max_steps_per_frame: int = max_steps_per_frame
        self.max_elapsed: float = max_elapsed
        self.accumulated: float = 0.0
        self._steps_this_frame: int = 0

    def reset(self) -> None:
        """Forget accumulated time, e.g. when a new game starts."""
        self.accumulated = 0.0
        self._steps_this_frame = 0

    def advance(self, elapsed: float) -> None:
        """Start a frame by adding its (clamped) elapsed time."""
        self.accumulated += min(max(elapsed, 0.0), self.max_elapsed)
        self._steps_this_frame = 0

    def take_step(self, interval: float) -> bool:
        """Consume one step of `interval` seconds if it is due this frame.

        Call in a loop, re-reading the interval each time, until it returns
        False. Hitting the per-frame cap drops the backlog to at most one
        interval, so the next frame resumes at the normal rate.
        """
        if self.accumulated < interval:
            return False
        if self._steps_this_frame >= self.max_steps_per_frame:
            self.accumulated = min(self.accumulated, interval)
            return False
        self.accumulated -= interval
        self._steps_this_frame += 1
        return True

    def progress(self, interval: float) -> float:
        """Fraction of the way to the next step, clamped to ``[0, 1]``."""
        return min(max(self.accumulated / interval, 0.0), 1.0)


# Floor on a scheduled wake, so an overdue (or float-early) step re-fires
# promptly without ever asking the timer for a zero or negative delay.
MIN_WAKE_DELAY = 0.001

# Fraction of a substep within which the clock counts as on a boundary.
_BOUNDARY_TOLERANCE = 1e-6


def next_wake_delay(
    interval: float,
    accumulated: float,
    frame_interval: float,
    substeps: int = 1,
) -> float:
    """Seconds until the loop should next wake to run a step or draw a substep.

    With one substep this is the time left until the next step is due. With
    more, it is the time until the next of `substeps` equal boundaries within
    the step. Wakes are never closer than a frame, except to meet the step
    deadline itself: intervals shorter than a frame wake once per frame and the
    clock batches the steps due, and substeps shorter than a frame are drawn at
    whatever boundary each frame reaches.
    """
    if interval < frame_interval:
        return frame_interval
    until_step = interval - accumulated
    substep = interval / substeps
    if substep < frame_interval:
        return max(min(frame_interval, until_step), MIN_WAKE_DELAY)
    # The tolerance treats a clock a hair short of a boundary as on it, so
    # float rounding cannot schedule a spurious near-zero wake.
    boundary = (math.floor(accumulated / substep + _BOUNDARY_TOLERANCE) + 1) * substep
    return max(min(boundary - accumulated, until_step), MIN_WAKE_DELAY)
