
"""
GARRY V7 — PAPER Trading Session

Runs public market-data analysis in a background thread.
PAPER only. This module never places LIVE orders.
"""

from threading import Lock, Thread

from kivy.clock import Clock

from app.state import APPROVED_SYMBOLS
from data.delta_public import DeltaAPIError
from strategy.auto_paper_engine import AutoPaperEngine


class TradingSession:
    """Background runner for the PAPER trading engine."""

    def __init__(self, on_update=None, on_error=None):
        self.on_update = on_update or (lambda result: None)
        self.on_error = on_error or (lambda message: None)

        self.mode = "PAPER"
        self.running = False
        self.event = None
        self.engine = None

        self._busy = Lock()
        self._state_lock = Lock()
        self._generation = 0

    def _send_update(self, result, generation=None):
        """Deliver updates on Kivy's main/UI thread."""

        def deliver(_dt):
            with self._state_lock:
                if generation is not None:
                    if generation != self._generation:
                        return
                    if not self.running and result.get("status") != "PAPER_STOPPED":
                        return

            self.on_update(result)

        Clock.schedule_once(deliver, 0)

    def _send_error(self, message, generation):
        """Deliver errors on Kivy's main/UI thread."""

        def deliver(_dt):
            with self._state_lock:
                if generation != self._generation or not self.running:
                    return

            self.on_error(message)

        Clock.schedule_once(deliver, 0)

    def start_paper(self, symbol="BTCUSD"):
        """Start PAPER analysis for an approved market symbol."""

        symbol = symbol.upper().strip()

        with self._state_lock:
            if self.running:
                return

            if self.mode != "PAPER":
                raise RuntimeError("Only PAPER mode is permitted.")

            if symbol not in APPROVED_SYMBOLS:
                raise ValueError(
                    f"Unsupported symbol: {symbol}"
                )

            self._generation += 1
            generation = self._generation

            self.engine = AutoPaperEngine(
                symbol=symbol,
                resolution="5m",
                quantity=1.0,
            )

            self.running = True
            self.event = Clock.schedule_interval(
                lambda dt: self._run_cycle(dt, generation),
                10,
            )

        self._send_update(
            {
                "status": "PAPER_STARTING",
                "mode": "PAPER",
                "symbol": symbol,
                "live_orders_enabled": False,
                "message": "PAPER session started; waiting for market data.",
            },
            generation,
        )

    def _run_cycle(self, _dt, generation):
        """Launch engine work without blocking the UI thread."""

        with self._state_lock:
            if not self.running or generation != self._generation:
                return

        if not self._busy.acquire(blocking=False):
            return

        worker = Thread(
            target=self._worker_cycle,
            args=(generation,),
            name="GARRY-PAPER-Worker",
            daemon=True,
        )

        try:
            worker.start()
        except Exception:
            self._busy.release()
            raise

    def _worker_cycle(self, generation):
        try:
            with self._state_lock:
                if not self.running or generation != self._generation:
                    return
                engine = self.engine

            if engine is None:
                raise RuntimeError("PAPER engine is not initialized.")

            result = engine.run_once()

            if not isinstance(result, dict):
                result = {
                    "status": "PAPER_UPDATE",
                    "result": result,
                }

            result["mode"] = "PAPER"
            result["live_orders_enabled"] = False

            self._send_update(result, generation)

        except (DeltaAPIError, ValueError, RuntimeError) as exc:
            self._send_error(str(exc), generation)

        except Exception as exc:
            self._send_error(
                f"PAPER engine error: {type(exc).__name__}: {exc}",
                generation,
            )

        finally:
            self._busy.release()

    def change_symbol(self, symbol):
        """Change symbol only when the session is stopped."""

        symbol = symbol.upper().strip()

        if symbol not in APPROVED_SYMBOLS:
            raise ValueError(f"Unsupported symbol: {symbol}")

        with self._state_lock:
            if self.running:
                raise RuntimeError(
                    "Stop the PAPER session before changing symbol."
                )

            if self.engine is not None:
                self.engine.symbol = symbol

    def stop(self):
        """Stop future cycles. An in-flight HTTP request may finish."""

        with self._state_lock:
            self.running = False
            self._generation += 1

            if self.event is not None:
                self.event.cancel()
                self.event = None

        self._send_update(
            {
                "status": "PAPER_STOPPED",
                "mode": "PAPER",
                "live_orders_enabled": False,
                "message": "PAPER session stopped.",
            }
        )
