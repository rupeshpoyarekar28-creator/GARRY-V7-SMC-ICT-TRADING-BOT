
"""
GARRY V7 — PAPER / LIVE Mode Controller

PAPER is the default.
LIVE stays blocked until a verified Delta execution adapter
and exchange-side risk protections are available.
"""

from dataclasses import dataclass
from typing import Literal

from strategy.execution_router import (
    ExecutionRouter,
    LiveTradingNotReady,
)

Mode = Literal["PAPER", "LIVE"]


@dataclass
class ModeStatus:
    mode: Mode = "PAPER"
    live_enabled: bool = False
    trading_enabled: bool = True
    message: str = "PAPER mode selected."


class ModeController:
    """Central mode selection for the app and execution router."""

    def __init__(self, router: ExecutionRouter | None = None):
        self.router = router or ExecutionRouter()
        self.status = ModeStatus()

    def select_mode(self, mode: str) -> ModeStatus:
        mode = mode.strip().upper()

        if mode not in ("PAPER", "LIVE"):
            raise ValueError("Choose PAPER or LIVE.")

        if mode == "PAPER":
            self.router.set_mode("PAPER")
            self.status = ModeStatus(
                mode="PAPER",
                live_enabled=False,
                trading_enabled=True,
                message="PAPER mode selected. Virtual trades only.",
            )
            self.router.enable_trading()
            return self.status

        # Selecting LIVE never automatically enables real orders.
        self.router.set_mode("LIVE")
        self.status = ModeStatus(
            mode="LIVE",
            live_enabled=False,
            trading_enabled=True,
            message=(
                "LIVE selected but NOT ARMED. "
                "Verified Delta API execution is required."
            ),
        )

        return self.status

    def enable_live(self, confirmation: str) -> ModeStatus:
        """
        This will fail closed until a verified live adapter
        has been configured in the router.
        """
        try:
            self.router.arm_live(confirmation)
        except LiveTradingNotReady:
            self.status.mode = "LIVE"
            self.status.live_enabled = False
            self.status.message = (
                "LIVE BLOCKED: Delta live adapter is not ready."
            )
            raise

        self.status = ModeStatus(
            mode="LIVE",
            live_enabled=True,
            trading_enabled=True,
            message="LIVE adapter armed. Verify all exchange safeguards.",
        )
        return self.status

    def emergency_stop(self) -> ModeStatus:
        self.router.disarm_live()
        self.status.trading_enabled = False
        self.status.live_enabled = False
        self.status.message = (
            "STOPPED. Restart and verify state before trading again."
        )
        return self.status

    def get_status(self) -> dict:
        return {
            "mode": self.status.mode,
            "live_enabled": self.status.live_enabled,
            "trading_enabled": self.status.trading_enabled,
            "message": self.status.message,
        }
