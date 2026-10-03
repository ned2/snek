# Make is the development lifecycle interface

Decided 2026-08-27 (issue 0021); implemented 2026-10-03.

The local quality gate (lockfile, lint, formatting, types, tests with a coverage floor,
dependency audit, distribution checks and isolated install smoke tests) began as one Python
script run by the pre-push hook. It worked, but offered only all or nothing: a developer could
not run one stage, and future CI would have had to call the same coarse script or copy its
commands. A `Makefile` now gives every stage a named target (`make help` lists them),
`make quality` runs them all, and the pre-push hook and CI call the same targets. pre-commit keeps
the fast commit-stage hooks. Make is familiar, ubiquitous on the platforms Snek is developed on,
and adds no environment manager beside uv; Windows support for the lifecycle itself is not a
requirement.

Make orchestrates, Python does the procedural work. Inspecting archive contents stays in
`scripts/check_distribution.py`, and the pre-push check stays in `scripts/check_pushed_ref.py`.
pre-commit names the pushed commit but runs hooks in the developer's checkout, where staged or
unstaged changes could make a broken commit pass, so the helper checks the commit out in a
temporary detached worktree, runs that revision's own `make quality` there and always removes
it. In shell that would need `mktemp` and traps; in Python it is short and unit-tested.

## Considered options

- **Keep the Python script**: portable and robust, but one coarse command, and a lifecycle
  interface of its own that CI would have to wrap.
- **Put the stages in pre-commit configuration**: ordered stages sharing build outputs fit
  independent hooks poorly, and the hook file would become the only lifecycle interface.
- **tox, Nox or Hatch environments**: good named sessions and matrices, but another environment
  layer beside uv; the Python version matrix belongs in hosted CI.
- **A parallel target graph**: pytest already runs on up to eight workers, so overlapping the
  other stages would save a few seconds at most while interleaving their output.

## Consequences

- Every target is phony, so gates always run. The gate's artifacts live in the ignored
  `.quality/` directory, which builds exclude explicitly, so a developer's own `.coverage` is
  never replaced; deletions are confined to fixed `.quality/` paths.
- The Makefile declares `.NOTPARALLEL`: stages share `.quality/`, so `make -j` runs the same
  serial, fail-fast sequence.
- The worktree's gate gets its own uv environment: the tracked `.envrc` exports an absolute
  `UV_PROJECT_ENVIRONMENT` for the developer's checkout, which would otherwise make it sync the
  developer's `.venv` against the pushed revision.
- The orchestration is tested through `make --dry-run` output and the helper's unit tests.
