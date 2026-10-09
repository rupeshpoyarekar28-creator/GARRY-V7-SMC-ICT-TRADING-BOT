
"""
GARRY V7 — PAPER Trading Session

Connects the existing AutoPaperEngine to Kivy's scheduler.
PAPER only. This module never places LIVE orders.
"""

from threading import Lock

from kivy.clock import Clock

from strategy.auto_paper_engine import AutoPaperEngine
from data.delta_public import DeltaAPIError


class TradingSession:
    def __init__(self, on_update=None, on_error=None):
        self.on_update = on_update or (lambda result: None)
        self.on_error = on_error or (lambda message: None)

        self.mode = "PAPER"
        self.running = False
        self.event = None
        self._busy = Lock()
        self.engine = None

    def start_paper(self, symbol="BTCUSD"):
        """Start periodic PAPER analysis; never sends exchange orders."""
        if self.running:
            return

        if self.mode != "PAPER":
            raise RuntimeError("Only PAPER mode is enabled in this session.")

        self.engine = AutoPaperEngine(
            symbol=symbol,
            resolution="5m",
            quantity=1.0,
        )

        self.running = True
        self.event = Clock.schedule_interval(self._run_cycle, 10)
        self.on_update({
            "status": "PAPER_STARTING",
            "mode": "PAPER",
            "symbol": symbol,
            "message": "Paper analysis scheduled.",
        })

    def _run_cycle(self, _dt):
        if not self.running or not self.engine:
            return

        # Prevent overlapping analysis cycles.
        if not self._busy.acquire(blocking=False):
            return

        try:
            result = self.engine.run_once()
            self.on_update(result)
        except (DeltaAPIError, ValueError, RuntimeError) as exc:
            self.on_error(str(exc))
        except Exception as exc:
            # Report the error rather than silently claiming success.
            self.on_error(
                f"Unexpected PAPER engine error: {type(exc).__name__}: {exc}"
            )
        finally:
            self._busy.release()

    def change_symbol(self, symbol):
        if self.running:
            raise RuntimeError("Stop PAPER session before changing symbol.")

        if symbol not in (
            "BTCUSD", "XAUTUSD", "ETHUSD", "PAXGUSD",
            "SOLUSD", "XRPUSD", "UNIUSD",
        ):
            raise ValueError("Symbol is not approved.")

        if self.engine:
            self.engine.symbol = symbol

    def stop(self):
        self.running = False

        if self.event is not None:
            self.event.cancel()
            self.event = None

        self.on_update({
            "status": "PAPER_STOPPED",
            "mode": "PAPER",
            "message": "Scheduler stopped.",
        })
