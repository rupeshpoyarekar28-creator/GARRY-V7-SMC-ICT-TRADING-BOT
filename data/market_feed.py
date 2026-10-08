"""
GARRY V7 SMC ICT TRADING BOT

Delta Exchange India - Market Feed

STEP 2:
- Discovers BTC perpetual symbol
- Fetches live ticker data
- Provides recent OHLC candles
- No API key
- No authentication
- No order placement
- No real trading
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from data.delta_public import (
    DeltaPublicAPIError,
    DeltaPublicClient,
)


@dataclass(frozen=True)
class MarketSnapshot:
    """Current market information."""

    symbol: str
    price: float
    bid: float
    ask: float
    volume: float
    timestamp: float
    status: str
    error: str = ""


class DeltaMarketFeed:
    """
    Safe public-data market feed.

    This class only reads public market data.
    It cannot place orders.
    """

    def __init__(
        self,
        symbol: Optional[str] = None,
        poll_interval: float = 5.0,
        timeout: int = 10,
    ):
        self.client = DeltaPublicClient(timeout=timeout)

        self.symbol = symbol
        self.poll_interval = max(
            2.0,
            float(poll_interval),
        )

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._snapshot = MarketSnapshot(
            symbol=symbol or "",
            price=0.0,
            bid=0.0,
            ask=0.0,
            volume=0.0,
            timestamp=0.0,
            status="DISCONNECTED",
            error="",
        )

        self._callbacks: list[
            Callable[[MarketSnapshot], None]
        ] = []

    # ---------------------------------------------------------
    # CALLBACKS
    # ---------------------------------------------------------

    def add_callback(
        self,
        callback: Callable[[MarketSnapshot], None],
    ) -> None:
        """Register a callback for new market snapshots."""

        if not callable(callback):
            raise TypeError("callback must be callable")

        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def remove_callback(
        self,
        callback: Callable[[MarketSnapshot], None],
    ) -> None:
        """Remove a previously registered callback."""

        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def _notify_callbacks(
        self,
        snapshot: MarketSnapshot,
    ) -> None:
        """Notify registered callbacks safely."""

        with self._lock:
            callbacks = list(self._callbacks)

        for callback in callbacks:
            try:
                callback(snapshot)
            except Exception:
                # UI callback failure must not stop market feed.
                continue

    # ---------------------------------------------------------
    # SNAPSHOT
    # ---------------------------------------------------------

    def get_snapshot(self) -> MarketSnapshot:
        """Return the latest market snapshot."""

        with self._lock:
            return self._snapshot

    def _set_snapshot(
        self,
        snapshot: MarketSnapshot,
    ) -> None:
        with self._lock:
            self._snapshot = snapshot

    # ---------------------------------------------------------
    # SYMBOL DISCOVERY
    # ---------------------------------------------------------

    def discover_symbol(self) -> str:
        """
        Discover an active BTC perpetual product.

        The symbol is obtained from Delta product metadata.
        """

        product = self.client.find_btc_perpetual()

        if not product:
            raise DeltaPublicAPIError(
                "No active BTC perpetual product found"
            )

        symbol = str(
            product.get("symbol", "")
        ).strip()

        if not symbol:
            raise DeltaPublicAPIError(
                "Delta returned BTC product without symbol"
            )

        self.symbol = symbol

        return symbol

    # ---------------------------------------------------------
    # NUMBER CONVERSION
    # ---------------------------------------------------------

    @staticmethod
    def _number(
        value,
        default: float = 0.0,
    ) -> float:
        """Safely convert API value to float."""

        try:
            if value is None:
                return default

            return float(value)

        except (TypeError, ValueError):
            return default

    # ---------------------------------------------------------
    # TICKER PARSING
    # ---------------------------------------------------------

    def _parse_ticker(
        self,
        ticker: dict,
    ) -> MarketSnapshot:
        """Convert Delta ticker response to MarketSnapshot."""

        symbol = str(
            ticker.get("symbol")
            or self.symbol
            or ""
        )

        price = self._number(
            ticker.get("close")
            or ticker.get("last_price")
            or ticker.get("price")
        )

        bid = self._number(
            ticker.get("best_bid")
            or ticker.get("bid")
        )

        ask = self._number(
            ticker.get("best_ask")
            or ticker.get("ask")
        )

        volume = self._number(
            ticker.get("volume")
        )

        return MarketSnapshot(
            symbol=symbol,
            price=price,
            bid=bid,
            ask=ask,
            volume=volume,
            timestamp=time.time(),
            status="CONNECTED",
            error="",
        )

    # ---------------------------------------------------------
    # SINGLE MARKET UPDATE
    # ---------------------------------------------------------

    def update_once(self) -> MarketSnapshot:
        """
        Perform one public market-data update.

        IMPORTANT:
        No trading or order operation is performed.
        """

        try:
            # Discover the symbol if one was not supplied.
            if not self.symbol:
                self.discover_symbol()

            ticker = self.client.get_ticker(
                self.symbol
            )

            snapshot = self._parse_ticker(
                ticker
            )

            # Reject invalid market price.
            if snapshot.price <= 0:
                raise DeltaPublicAPIError(
                    "Delta returned invalid market price"
                )

            self._set_snapshot(snapshot)

            self._notify_callbacks(
                snapshot
            )

            return snapshot

        except Exception as exc:
            error_message = str(exc)

            snapshot = MarketSnapshot(
                symbol=self.symbol or "",
                price=0.0,
                bid=0.0,
                ask=0.0,
                volume=0.0,
                timestamp=time.time(),
                status="ERROR",
                error=error_message,
            )

            self._set_snapshot(snapshot)

            self._notify_callbacks(
                snapshot
            )

            return snapshot

    # ---------------------------------------------------------
    # BACKGROUND LOOP
    # ---------------------------------------------------------

    def _run_loop(self) -> None:
        """Run public market-data polling in background."""

        while self._running:
            started = time.monotonic()

            self.update_once()

            elapsed = (
                time.monotonic() - started
            )

            wait_time = max(
                0.0,
                self.poll_interval - elapsed,
            )

            if wait_time > 0:
                time.sleep(wait_time)

    # ---------------------------------------------------------
    # START
    # ---------------------------------------------------------

    def start(self) -> bool:
        """
        Start background market-data polling.

        Returns:
            True  = started
            False = already running
        """

        if self._running:
            return False

        self._running = True

        self._thread = threading.Thread(
            target=self._run_loop,
            name="garry-delta-market-feed",
            daemon=True,
        )

        self._thread.start()

        return True

    # ---------------------------------------------------------
    # STOP
    # ---------------------------------------------------------

    def stop(self) -> bool:
        """
        Stop background market-data polling.

        Returns:
            True  = stopped
            False = already stopped
        """

        if not self._running:
            return False

        self._running = False

        thread = self._thread

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(
                timeout=2.0
            )

        self._thread = None

        return True

    # ---------------------------------------------------------
    # RUNNING STATUS
    # ---------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Return True when background polling is active."""

        return self._running

    # ---------------------------------------------------------
    # RECENT CANDLES
    # ---------------------------------------------------------

    def get_recent_candles(
        self,
        resolution: str = "5m",
        count: int = 100,
    ) -> list[dict]:
        """
        Fetch recent OHLC candles.

        This uses public REST market data only.
        """

        if not self.symbol:
            self.discover_symbol()

        return self.client.get_recent_candles(
            symbol=self.symbol,
            resolution=resolution,
            count=count,
        )

    # ---------------------------------------------------------
    # CLOSE
    # ---------------------------------------------------------

    def close(self) -> None:
        """Stop the market feed."""

        self.stop()


# -------------------------------------------------------------
# MANUAL TEST
# -------------------------------------------------------------

if __name__ == "__main__":

    feed = DeltaMarketFeed(
        poll_interval=5.0,
        timeout=10,
    )

    try:

        snapshot = feed.update_once()

        print(
            "STATUS:",
            snapshot.status,
        )

        print(
            "SYMBOL:",
            snapshot.symbol,
        )

        print(
            "PRICE:",
            snapshot.price,
        )

        print(
            "BID:",
            snapshot.bid,
        )

        print(
            "ASK:",
            snapshot.ask,
        )

        print(
            "VOLUME:",
            snapshot.volume,
        )

        print(
            "ERROR:",
            snapshot.error,
        )

    finally:

        feed.close()
