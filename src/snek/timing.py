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

Framework-free (no Textual) so it can be unit-tested with plain numbers.
"""


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
