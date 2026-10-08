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
    DeltaPublicClient,
    DeltaPublicAPIError,
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
    # Callback registration
    # ---------------------------------------------------------

    def add_callback(
        self,
        callback: Callable[[MarketSnapshot], None],
    ) -> None:
        """
        Register a callback.

        The callback receives a MarketSnapshot whenever
        new market data is received.
        """

        if callback not in self._callbacks:
            self._callbacks.append(callback)

    # ---------------------------------------------------------
    # Snapshot
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
    # Symbol discovery
    # ---------------------------------------------------------

    def discover_symbol(self) -> str:
        """
        Discover an active BTC perpetual product.

        The symbol is obtained from Delta product metadata.
        """

        product = self.client.find_btc_perpetual()

        if not product:
