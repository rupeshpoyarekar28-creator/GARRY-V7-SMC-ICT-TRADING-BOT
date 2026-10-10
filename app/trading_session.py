
"""
GARRY V7 — PAPER Trading Session with safe recovery.
PAPER only. This module never places LIVE exchange orders.
"""

import logging
import os
import re
import threading
import time
import traceback
from logging.handlers import RotatingFileHandler

from kivy.clock import Clock

from app.state import APPROVED_SYMBOLS
from data.delta_public import DeltaAPIError
from strategy.auto_paper_engine import AutoPaperEngine


RETRY_INITIAL_SECONDS = 2.0
RETRY_MAX_SECONDS = 60.0
MAX_LOG_BYTES = 1_000_000
LOG_BACKUPS = 3


def _build_logger():
    """Create a rotating log without allowing logging failures to crash the app."""
    logger = logging.getLogger("garry_v7.recovery")

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)sZ | component=%(component)s | "
        "category=%(category)s | recovery=%(recovery)s | "
        "%(levelname)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    try:
        # Android should preferably use the app's writable data directory.
        os.makedirs("data", exist_ok=True)
        handler = RotatingFileHandler(
            os.path.join("data", "garry_errors.log"),
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUPS,
            encoding="utf-8",
        )
    except (OSError, ValueError):
        handler = logging.StreamHandler()

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


_LOGGER = _build_logger()


def _safe_message(message):
    """Redact common credential-shaped values before logging."""
    text = str(message)

    text = re.sub(
        r"(?i)(api[_ -]?(?:key|secret)|password|token|authorization)"
        r"(\s*[:=]\s*)[^\s,;]+",
        r"\1\2[REDACTED]",
        text,
    )

    return text[:1000]


def _log_event(category, message, recovery, level=logging.ERROR):
    """Logging is best-effort and must never break trading controls."""
    try:
        _LOGGER.log(
            level,
            _safe_message(message),
            extra={
                "component": "TradingSession",
                "category": str(category),
                "recovery": str(recovery),
            },
        )
    except Exception:
        pass


def _log_exception(category, exc, recovery):
    """Record exception type and traceback for debugging."""
    try:
        detail = (
            f"{type(exc).__name__}: {_safe_message(exc)}\n"
            f"{traceback.format_exc()}"
        )
        _log_event(category, detail, recovery)
    except Exception:
        _log_event(category, type(exc).__name__, recovery)


def _is_recoverable_market_error(exc):
    """Identify transient public market-data errors."""
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True

    if not isinstance(exc, DeltaAPIError):
        return False

    message = str(exc).upper()

    return any(
        marker in message
        for marker in (
            "NETWORK ERROR",
            "TIMEOUT",
            "CONNECTION",
            "HTTP ERROR 408",
            "HTTP ERROR 425",
            "HTTP ERROR 429",
            "HTTP ERROR 500",
            "HTTP ERROR 502",
            "HTTP ERROR 503",
            "HTTP ERROR 504",
            "NOT ENOUGH VALID CANDLES",
        )
    )


class TradingSession:
    """Single PAPER session manager with bounded retry and safe stopping."""

    def __init__(self, on_update=None, on_error=None):
        self.on_update = on_update or (lambda result: None)
        self.on_error = on_error or (lambda message: None)

        self.mode = "PAPER"
        self.running = False
        self.event = None
        self.engine = None

        self._busy = threading.Lock()
        self._state_lock = threading.RLock()
        self._generation = 0
        self._consecutive_failures = 0
        self._next_retry_at = 0.0

    def _send_update(self, result, generation=None):
        """Deliver UI updates on Kivy's main thread."""

        def deliver(_dt):
            with self._state_lock:
                if generation is not None:
                    if generation != self._generation:
                        return

                    if (
                        not self.running
                        and result.get("status") != "PAPER_STOPPED"
                    ):
                        return

            try:
                self.on_update(result)
            except Exception as exc:
                _log_exception(
                    "UI_UPDATE_CALLBACK",
                    exc,
                    "CALLBACK_FAILURE_RECORDED",
                )

        try:
            Clock.schedule_once(deliver, 0)
        except Exception as exc:
            _log_exception(
                "UI_UPDATE_SCHEDULE",
                exc,
                "CALLBACK_FAILURE_RECORDED",
            )

    def _send_error(self, message, generation=None):
        """Deliver an error message on Kivy's main thread."""

        def deliver(_dt):
            with self._state_lock:
                if (
                    generation is not None
                    and generation != self._generation
                ):
                    return

            try:
                self.on_error(str(message))
            except Exception as exc:
                _log_exception(
                    "UI_ERROR_CALLBACK",
                    exc,
                    "CALLBACK_FAILURE_RECORDED",
                )

        try:
            Clock.schedule_once(deliver, 0)
        except Exception as exc:
            _log_exception(
                "UI_ERROR_SCHEDULE",
                exc,
                "CALLBACK_FAILURE_RECORDED",
            )

    def start_paper(self, symbol="BTCUSD"):
        """Start virtual trading only; no exchange orders are placed."""
        if not isinstance(symbol, str):
            raise ValueError("Symbol must be text.")

        symbol = symbol.upper().strip()

        with self._state_lock:
            if self.running:
                _log_event(
                    "DUPLICATE_START",
                    "Paper session is already running.",
                    "EXISTING_SESSION_PRESERVED",
                    logging.WARNING,
                )
                return

            if self.mode != "PAPER":
                raise RuntimeError("Only PAPER mode is permitted.")

            if symbol not in APPROVED_SYMBOLS:
                _log_event(
                    "INVALID_SYMBOL",
                    "Rejected unsupported symbol.",
                    "START_BLOCKED",
                    logging.WARNING,
                )
                raise ValueError("Unsupported symbol.")

            self._generation += 1
            generation = self._generation

            try:
                self.engine = AutoPaperEngine(
                    symbol=symbol,
                    resolution="5m",
                    quantity=1.0,
                )
            except Exception as exc:
                _log_exception(
                    "ENGINE_INIT",
                    exc,
                    "START_BLOCKED",
                )
                raise

            self._consecutive_failures = 0
            self._next_retry_at = 0.0
            self.running = True

            try:
                self.event = Clock.schedule_interval(
                    lambda dt: self._run_cycle(dt, generation),
                    10,
                )
            except Exception as exc:
                self.running = False
                self.engine = None
                _log_exception(
                    "SCHEDULER_INIT",
                    exc,
                    "START_ROLLED_BACK",
                )
                raise RuntimeError(
                    "Could not schedule Paper Trading cycle."
                ) from exc

        _log_event(
            "SESSION_START",
            "PAPER session started.",
            "PAPER_ONLY_STARTED",
            logging.INFO,
        )

        self._send_update(
            {
                "status": "PAPER_STARTING",
                "mode": "PAPER",
                "symbol": symbol,
                "live_orders_enabled": False,
                "message": (
                    "Paper session started; waiting for public market data."
                ),
            },
            generation,
        )

    def _run_cycle(self, _dt, generation):
        """Schedule one worker at a time and respect retry backoff."""
        with self._state_lock:
            if not self.running or generation != self._generation:
                return

            if time.monotonic() < self._next_retry_at:
                return

        if not self._busy.acquire(blocking=False):
            _log_event(
                "DUPLICATE_CYCLE",
                "Cycle skipped because previous worker is active.",
                "SKIPPED",
                logging.WARNING,
            )
            return

        worker = threading.Thread(
            target=self._worker_cycle,
            args=(generation,),
            name="GARRY-PAPER-Worker",
            daemon=True,
        )

        try:
            worker.start()
        except Exception as exc:
            self._busy.release()

            _log_exception(
                "WORKER_START",
                exc,
                "SESSION_PAUSED",
            )

            self._pause_session(
                generation,
                "Paper worker could not start.",
            )

            self._send_error(
                "Paper worker could not start. Paper Trading was paused.",
                None,
            )

    def _worker_cycle(self, generation):
        """Run one virtual-trading cycle with detailed diagnostics."""
        try:
            with self._state_lock:
                if (
                    not self.running
                    or generation != self._generation
                ):
                    return

                engine = self.engine

            if engine is None:
                raise RuntimeError(
                    "PAPER engine is not initialized."
                )

            result = engine.run_once()

            if not isinstance(result, dict):
                result = {
                    "status": "PAPER_UPDATE",
                    "result": str(result),
                }

            # Explicitly mark all session output as virtual.
            result["mode"] = "PAPER"
            result["live_orders_enabled"] = False

            with self._state_lock:
                if (
                    not self.running
                    or generation != self._generation
                ):
                    return

                self._consecutive_failures = 0
                self._next_retry_at = 0.0

            _log_event(
                "CYCLE_OK",
                result.get("status", "UPDATED"),
                "CONTINUE",
                logging.INFO,
            )

            self._send_update(result, generation)

        except Exception as exc:
            error_detail = (
                f"{type(exc).__name__}: {_safe_message(exc)}"
            )

            _log_exception(
                "PAPER_CYCLE_EXCEPTION",
                exc,
                "CLASSIFYING_ERROR",
            )

            if _is_recoverable_market_error(exc):
                with self._state_lock:
                    if (
                        not self.running
                        or generation != self._generation
                    ):
                        return

                    self._consecutive_failures += 1
                    attempt = self._consecutive_failures

                    delay = min(
                        RETRY_INITIAL_SECONDS
                        * (2 ** min(attempt - 1, 10)),
                        RETRY_MAX_SECONDS,
                    )

                    self._next_retry_at = (
                        time.monotonic() + delay
                    )

                _log_event(
                    "TRANSIENT_MARKET_DATA",
                    error_detail,
                    f"RETRY_IN_{delay:g}_SECONDS",
                )

                self._send_error(
                    f"Temporary market-data error: {error_detail}. "
                    f"Retry in {delay:g} seconds.",
                    generation,
                )

            else:
                _log_event(
                    "UNEXPECTED_ENGINE_ERROR",
                    error_detail,
                    "SESSION_PAUSED",
                )

                self._pause_session(
                    generation,
                    f"Paper engine error: {error_detail}",
                )

                self._send_error(
                    "Paper Trading paused safely after an unexpected "
                    f"error: {error_detail}. Check garry_errors.log.",
                    None,
                )

        finally:
            self._busy.release()

    def _pause_session(self, generation, reason):
        """Stop the scheduler without placing any exchange orders."""
        with self._state_lock:
            if generation != self._generation:
                return

            self.running = False
            self._generation += 1

            if self.event is not None:
                try:
                    self.event.cancel()
                except Exception as exc:
                    _log_exception(
                        "SCHEDULER_CANCEL",
                        exc,
                        "SAFE_STOP_CONTINUED",
                    )

                self.event = None

        _log_event(
            "SAFE_STOP",
            reason,
            "MANUAL_REVIEW_REQUIRED",
        )

        self._send_update(
            {
                "status": "PAPER_ERROR",
                "mode": "PAPER",
                "live_orders_enabled": False,
                "message": str(reason),
            }
        )

    def change_symbol(self, symbol):
        """Reject invalid symbols and preserve active-session consistency."""
        if not isinstance(symbol, str):
            raise ValueError("Symbol must be text.")

        symbol = symbol.upper().strip()

        if symbol not in APPROVED_SYMBOLS:
            _log_event(
                "INVALID_SYMBOL",
                "Rejected unsupported symbol.",
                "OLD_CONFIGURATION_PRESERVED",
                logging.WARNING,
            )
            raise ValueError("Unsupported symbol.")

        with self._state_lock:
            if self.running:
                raise RuntimeError(
                    "Stop the PAPER session before changing symbol."
                )

            if self.engine is not None:
                self.engine.symbol = symbol

    def stop(self):
        """Stop the virtual session and invalidate pending callbacks."""
        with self._state_lock:
            was_running = self.running

            self.running = False
            self._generation += 1

            if self.event is not None:
                try:
                    self.event.cancel()
                except Exception as exc:
                    _log_exception(
                        "SCHEDULER_CANCEL",
                        exc,
                        "STOP_CONTINUED",
                    )

                self.event = None

        _log_event(
            "SESSION_STOP",
            "PAPER session stopped.",
            "SCHEDULER_CANCELLED",
            logging.INFO,
        )

        self._send_update(
            {
                "status": "PAPER_STOPPED",
                "mode": "PAPER",
                "live_orders_enabled": False,
                "was_running": was_running,
                "message": "PAPER session stopped.",
            }
        )
