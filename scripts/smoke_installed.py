"""Smoke-test application resources from an installed Snek distribution."""

from __future__ import annotations

import asyncio
from importlib.resources import files

from snek.app import SnakeApp


async def check_installed_app() -> None:
    """Load packaged resources and mount the application headlessly."""
    stylesheet = files("snek").joinpath("styles.css")
    if not stylesheet.is_file():
        raise RuntimeError("Installed distribution is missing snek/styles.css")

    app = SnakeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()


def main() -> int:
    """Run the installed application probe."""
    asyncio.run(check_installed_app())
    print("Installed application resources loaded successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
