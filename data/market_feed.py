"""
GARRY V7 SMC ICT TRADING BOT

STEP 4 - Delta Live Market Feed

Purpose:
- Delta Exchange India public market data
- Locked 7 trading pairs
- REST ticker fallback
- Thread-safe snapshots
- Stale-data detection
- Reconnect-friendly architecture

IMPORTANT:
- No API key
- No private authentication
- No order placement
- No real trading
- WebSocket dependency is optional
- REST remains available as fallback

Primary future architecture:
    Delta WebSocket
          |
          v
    MarketFeed Engine
          |
          +--> 7 pair snapshots
          |
          +--> SMC/ICT
          |
          +--> Risk Engine

For the current stable Android build, the module must remain
dependency-light. If websocket-client is not packaged yet,
REST fallback remains functional.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from data.delta_public import (
    APPROVED_SYMBOLS,
    DeltaAPIError,
    DeltaPublicClient,
)


DELTA_PUBLIC_WS_URL = (
    "wss://public-socket.india.delta.exchange"
)

DEFAULT_REST_INTERVAL = 5.0
DEFAULT_STALE_AFTER = 15.0


# ================================================================
# MARKET SNAPSHOT
# ================================================================

@dataclass
class MarketSnapshot:
    symbol: str

    price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    volume: float = 0.0

    timestamp: float = 0.0

    status: str = "WAITING"
    source: str = "NONE"

    error: str = ""

    @property
    def is_stale(
        self,
        stale_after: float = DEFAULT_STALE_AFTER,
    ) -> bool:

        if self.timestamp <= 0:
            return True

        return (
            time.time() - self.timestamp
        ) > stale_after


# ================================================================
# MARKET FEED
# ================================================================

class DeltaMarketFeed:
    """
    Public Delta market-data engine.

    Current stable mode:
        REST polling

    Architecture prepared for:
        WebSocket primary
        REST fallback
    """

    def __init__(
        self,
        symbols: Optional[tuple[str, ...]] = None,
        rest_interval: float = DEFAULT_REST_INTERVAL,
        stale_after: float = DEFAULT_STALE_AFTER,
    ):

        requested_symbols = (
            symbols
            if symbols is not None
            else APPROVED_SYMBOLS
        )

        # --------------------------------------------------------
        # Security: never allow symbols outside approved list.
        # --------------------------------------------------------

        self.symbols = tuple(
            symbol.upper().strip()
            for symbol in requested_symbols
            if symbol.upper().strip()
            in APPROVED_SYMBOLS
        )

        self.rest_interval = max(
            2.0,
            float(rest_interval),
        )

        self.stale_after = max(
            5.0,
            float(stale_after),
        )

        self.client = DeltaPublicClient()

        self._snapshots: dict[str, MarketSnapshot] = {
            symbol: MarketSnapshot(
                symbol=symbol
            )
            for symbol in self.symbols
        }

        self._callbacks: list[
            Callable[[MarketSnapshot], None]
        ] = []

        self._lock = threading.RLock()

        self._running = False
        self._thread: Optional[
            threading.Thread
        ] = None

        self._last_error = ""
        self._connection_status = "DISCONNECTED"

        self._ws_available = False

        self._stop_event = threading.Event()

    # ============================================================
    # CALLBACKS
    # ============================================================

    def add_callback(
        self,
        callback: Callable[
            [MarketSnapshot],
            None,
        ],
    ) -> None:

        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_callback(
        self,
        callback: Callable[
            [MarketSnapshot],
            None,
        ],
    ) -> None:

        if callback in self._callbacks:
            self._callbacks.remove(callback)

    # ============================================================
    # SNAPSHOT ACCESS
    # ============================================================

    def get_snapshot(
        self,
        symbol: str,
    ) -> Optional[MarketSnapshot]:

        symbol = symbol.upper().strip()

        with self._lock:

            snapshot = self._snapshots.get(
                symbol
            )

            if snapshot is None:
                return None

            return MarketSnapshot(
                symbol=snapshot.symbol,
                price=snapshot.price,
                bid=snapshot.bid,
                ask=snapshot.ask,
                volume=snapshot.volume,
                timestamp=snapshot.timestamp,
                status=snapshot.status,
                source=snapshot.source,
                error=snapshot.error,
            )

    def get_all_snapshots(
        self,
    ) -> dict[str, MarketSnapshot]:

        with self._lock:

            return {
                symbol: MarketSnapshot(
                    symbol=snapshot.symbol,
                    price=snapshot.price,
                    bid=snapshot.bid,
                    ask=snapshot.ask,
                    volume=snapshot.volume,
                    timestamp=snapshot.timestamp,
                    status=snapshot.status,
                    source=snapshot.source,
                    error=snapshot.error,
                )
                for symbol, snapshot
                in self._snapshots.items()
            }

    # ============================================================
    # CONNECTION STATUS
    # ============================================================

    @property
    def connection_status(self) -> str:

        with self._lock:
            return self._connection_status

    @property
    def last_error(self) -> str:

        with self._lock:
            return self._last_error

    def _set_connection_status(
        self,
        status: str,
        error: str = "",
    ) -> None:

        with self._lock:
            self._connection_status = status
            self._last_error = error

    # ============================================================
    # START / STOP
    # ============================================================

    def start(self) -> None:

        if self._running:
            return

        self._running = True
        self._stop_event.clear()

        self._set_connection_status(
            "CONNECTING"
        )

        self._thread = threading.Thread(
            target=self._run_loop,
            name="GARRY-V7-MarketFeed",
            daemon=True,
        )

        self._thread.start()

    def stop(self) -> None:

        self._running = False
        self._stop_event.set()

        self._set_connection_status(
            "DISCONNECTED"
        )

        thread = self._thread

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):

            thread.join(
                timeout=3.0
            )

        self._thread = None

    # ============================================================
    # MAIN LOOP
    # ============================================================

    def _run_loop(self) -> None:

        while (
            self._running
            and not self._stop_event.is_set()
        ):

            try:

                self._set_connection_status(
                    "REST_FALLBACK"
                )

                self._poll_all_symbols()

            except Exception as exc:

                self._set_connection_status(
                    "ERROR",
                    str(exc),
                )

            self._stop_event.wait(
                self.rest_interval
            )

    # ============================================================
    # REST POLLING
    # ============================================================

    def _poll_all_symbols(self) -> None:

        successful_updates = 0

        for symbol in self.symbols:

            if (
                not self._running
                or self._stop_event.is_set()
            ):
                break

            try:

                ticker = self.client.get_ticker(
                    symbol
                )

                snapshot = self._parse_ticker(
                    symbol,
                    ticker,
                )

                self._update_snapshot(
                    snapshot
                )

                successful_updates += 1

            except (
                DeltaAPIError,
                urllib.error.URLError,
                TimeoutError,
                ValueError,
                TypeError,
            ) as exc:

                self._mark_error(
                    symbol,
                    str(exc),
                )

        if successful_updates > 0:

            self._set_connection_status(
                "CONNECTED"
            )

        else:

            self._set_connection_status(
                "OFFLINE",
                "No market data received",
            )

        self._refresh_stale_states()

    # ============================================================
    # TICKER PARSER
    # ============================================================

    def _parse_ticker(
        self,
        symbol: str,
        payload: dict,
    ) -> MarketSnapshot:

        if not isinstance(payload, dict):
            raise ValueError(
                "Invalid ticker payload"
            )

        ticker = payload.get(
            "result",
            payload,
        )

        if not isinstance(ticker, dict):
            raise ValueError(
                "Invalid ticker result"
            )

        price = self._to_float(
            ticker.get("close")
        )

        if price <= 0:

            price = self._to_float(
                ticker.get("mark_price")
            )

        quotes = ticker.get(
            "quotes"
        )

        if not isinstance(
            quotes,
            dict,
        ):
            quotes = {}

        bid = self._to_float(
            quotes.get("best_bid")
        )

        if bid <= 0:
            bid = self._to_float(
                ticker.get("best_bid")
            )

        ask = self._to_float(
            quotes.get("best_ask")
        )

        if ask <= 0:
            ask = self._to_float(
                ticker.get("best_ask")
            )

        volume = self._to_float(
            ticker.get("volume")
        )

        if price <= 0:
            raise ValueError(
                "Invalid market price"
            )

        return MarketSnapshot(
            symbol=symbol,
            price=price,
            bid=bid,
            ask=ask,
            volume=volume,
            timestamp=time.time(),
            status="LIVE",
            source="REST",
            error="",
        )

    # ============================================================
    # SNAPSHOT UPDATE
    # ============================================================

    def _update_snapshot(
        self,
        snapshot: MarketSnapshot,
    ) -> None:

        callbacks: list[
            Callable[[MarketSnapshot], None]
        ]

        with self._lock:

            self._snapshots[
                snapshot.symbol
            ] = snapshot

            callbacks = list(
                self._callbacks
            )

        for callback in callbacks:

            try:
                callback(
                    snapshot
                )

            except Exception:
                # Callback errors must never
                # stop market-data processing.
                continue

    # ============================================================
    # ERROR HANDLING
    # ============================================================

    def _mark_error(
        self,
        symbol: str,
        error: str,
    ) -> None:

        with self._lock:

            snapshot = self._snapshots.get(
                symbol
            )

            if snapshot is None:
                return

            snapshot.status = "ERROR"
            snapshot.error = error

    def _refresh_stale_states(self) -> None:

        with self._lock:

            for snapshot in (
                self._snapshots.values()
            ):

                if snapshot.is_stale(
                    self.stale_after
                ):

                    if snapshot.timestamp > 0:
                        snapshot.status = "STALE"

    # ============================================================
    # UTILITIES
    # ============================================================

    @staticmethod
    def _to_float(
        value,
    ) -> float:

        try:

            if value is None:
                return 0.0

            return float(value)

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

    # ============================================================
    # HEALTH
    # ============================================================

    def health(self) -> dict:

        snapshots = (
            self.get_all_snapshots()
        )

        live_count = 0
        stale_count = 0
        error_count = 0

        for snapshot in snapshots.values():

            if snapshot.status == "LIVE":
                live_count += 1

            elif snapshot.status == "STALE":
                stale_count += 1

            elif snapshot.status == "ERROR":
                error_count += 1

        return {
            "connection": self.connection_status,
            "symbols": len(self.symbols),
            "live": live_count,
            "stale": stale_count,
            "errors": error_count,
            "last_error": self.last_error,
        }


# ================================================================
# DEFAULT FEED FACTORY
# ================================================================

def create_market_feed(
    callback: Optional[
        Callable[[MarketSnapshot], None]
    ] = None,
) -> DeltaMarketFeed:

    feed = DeltaMarketFeed(
        symbols=APPROVED_SYMBOLS,
        rest_interval=DEFAULT_REST_INTERVAL,
        stale_after=DEFAULT_STALE_AFTER,
    )

    if callback is not None:
        feed.add_callback(
            callback
        )

    return feed
