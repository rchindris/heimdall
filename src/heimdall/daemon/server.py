"""Daemon mode — periodic scan and guard loop."""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import signal
import traceback
from pathlib import Path

from ..config import AdminConfig


def _setup_logging(config: AdminConfig) -> logging.Logger:
    """Set up logging for the daemon."""
    log_dir = config.profiles_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "daemon.log"

    logger = logging.getLogger("heimdall-daemon")
    logger.setLevel(logging.INFO)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    file_handler.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


class AdminDaemon:
    """Long-running daemon that periodically scans the machine and checks for drift."""

    def __init__(self, config: AdminConfig, recipe_path: str) -> None:
        self.config = config
        self.recipe_path = recipe_path
        self._shutdown = asyncio.Event()
        self._logger = _setup_logging(config)

    async def run(self) -> None:
        """Main daemon loop."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_signal)

        self._logger.info(
            f"heimdall daemon started "
            f"(interval={self.config.daemon_interval_minutes}m, "
            f"recipe={self.recipe_path})"
        )
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

        self._logger.info("heimdall daemon shutting down.")
        print("heimdall daemon shutting down.")

    async def _tick(self) -> None:
        """Run one scan + guard cycle."""
        from ..agent import run_guard, run_scan

        self._logger.info("Starting daemon tick: scan")
        print("\n--- Daemon tick: scanning ---")
        try:
            await run_scan(self.config)
            self._logger.info("Scan completed successfully")
        except Exception as e:
            self._logger.error(f"Scan error: {traceback.format_exc()}")
            print(f"Scan error:\n{traceback.format_exc()}")

        self._logger.info("Starting daemon tick: guard check")
        print("\n--- Daemon tick: guard check ---")
        try:
            await run_guard(self.config, self.recipe_path)
            self._logger.info("Guard check completed successfully")
        except Exception as e:
            self._logger.error(f"Guard error: {traceback.format_exc()}")
            print(f"Guard error:\n{traceback.format_exc()}")

    def _handle_signal(self) -> None:
        """Handle shutdown signals."""
        print("\nReceived shutdown signal.")
        self._logger.info("Received shutdown signal")
        self._shutdown.set()
