# Wake the game loop at each step's exact deadline

Decided 2026-09-23 (issue 0027); the stale-wake guard was added 2026-09-24.

The model advances in steps (one move of the snake) whose interval depends on the world, and that
interval is rarely a whole number of 60 Hz frames. `GameScreen` keeps time with `StepClock`, a
fixed-step accumulator: each wake of the loop credits the wall time since the last one and runs
every step that has come due, re-reading the interval before each, so a speed change applies from
the next step with no timer restart and a stall is clamped rather than replayed. The loop is driven
by one one-shot timer, which `_arm()` sets for the next step's exact deadline
(`timing.next_wake_delay()`) or, while movement is interpolated, for the next increment boundary
within the step. It never wakes more often than once a frame except to meet a deadline. The first
version of the accumulator woke on a fixed 60 Hz frame grid instead, so each step landed on the
next frame and consecutive gaps alternated by a frame (83 and 100 ms at a 90 ms interval), which
players saw as hiccups. Waking at deadlines made the gaps even (spread at the default speed fell
from about 7 ms to about 1 ms) and the loop wakes only when there is something to do.

Textual queues a timer's callback rather than calling it, so stopping a timer cannot recall a wake
that has already fired; that wake would then run a step and re-arm the loop after a pause or game
over. Each wake therefore carries the `_generation` it was armed in, `_disarm()` bumps the
generation, and `_on_wake` ignores wakes from an older one. Interpolation's frequent increment
wakes made this race common, which is when the guard was added.

## Considered options

- **A per-speed repeating timer** (the original loop), stopped and restarted after every speed
  change: it drifted (9.7 moves/s at a 100 ms interval), reset its phase on every restart, and fired
  an overdue step as soon as play resumed.
- **A fixed 60 Hz frame timer** feeding the accumulator: uneven step gaps, as above.
- **A one-shot at the deadline on top of the 60 Hz timer**: even steps without animation, but while
  repainting every frame it competed with the frame updates (outliers of about 34 ms), left a
  second timer to cancel, and re-armed every step at sub-frame intervals.

## Consequences

- Between wakes no time is credited, so pausing (or holding for a too-small terminal) credits the
  time already waited before stopping the timer, and resuming re-arms with the paused time
  discarded. The next step then comes after only the rest of its interval.
- `timer.stop()` alone does not stop the loop. Code and tests stop it with `_disarm()`, and `_arm()`
  is the only place that creates the timer.
