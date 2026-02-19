"""Daemon mode — periodic scan and guard loop."""

from __future__ import annotations

import asyncio
import signal
import traceback

from ..config import AdminConfig


class AdminDaemon:
    """Long-running daemon that periodically scans the machine and checks for drift."""

    def __init__(self, config: AdminConfig, recipe_path: str) -> None:
        self.config = config
        self.recipe_path = recipe_path
        self._shutdown = asyncio.Event()

    async def run(self) -> None:
        """Main daemon loop."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_signal)

        print(
            f"heimdall daemon started "
            f"(interval={self.config.daemon_interval_minutes}m, "
            f"recipe={self.recipe_path})"
        )

        while not self._shutdown.is_set():
            await self._tick()
            try:
                await asyncio.wait_for(
                    self._shutdown.wait(),
                    timeout=self.config.daemon_interval_minutes * 60,
                )
            except asyncio.TimeoutError:
                pass  # Normal — timeout means it's time for the next tick

        print("heimdall daemon shutting down.")

    async def _tick(self) -> None:
        """Run one scan + guard cycle."""
        from ..agent import run_guard, run_scan

        print("\n--- Daemon tick: scanning ---")
        try:
            await run_scan(self.config)
        except Exception:
            print(f"Scan error:\n{traceback.format_exc()}")

        print("\n--- Daemon tick: guard check ---")
        try:
            await run_guard(self.config, self.recipe_path)
        except Exception:
            print(f"Guard error:\n{traceback.format_exc()}")

    def _handle_signal(self) -> None:
        """Handle shutdown signals."""
        print("\nReceived shutdown signal.")
        self._shutdown.set()
