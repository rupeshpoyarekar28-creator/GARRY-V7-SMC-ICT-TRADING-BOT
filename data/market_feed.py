
"""
GARRY V7 — Delta Exchange India public market feed.

Features:
- Compatible with app.ui.DashboardUI.
- REST polling for all approved symbols, using independent workers.
- Optional compact ticker-message parsing.
- Thread-safe snapshots and callbacks.
- Honest OFFLINE / ERROR / STALE states.
- No API credentials and no real order placement.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from data.delta_public import (
    APPROVED_SYMBOLS,
    DeltaAPIError,
    DeltaPublicClient,
)

logger = logging.getLogger("garry_v7.market_feed")

POLL_INTERVAL_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 5
STALE_AFTER_SECONDS = 20.0


@dataclass
class MarketSnapshot:
    symbol: str
    last_price: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None
    status: str = "OFFLINE"
    source: str = "NONE"
    error: str = ""
    updated_at: float = 0.0
    updated_utc: str = ""

    @property
    def price(self):
        return self.last_price

    @property
    def is_stale(self):
        if self.updated_at <= 0:
            return True
        return time.time() - self.updated_at > STALE_AFTER_SECONDS

    def as_dict(self):
        return {
            "symbol": self.symbol,
            "last_price": self.last_price,
            "price": self.last_price,
            "bid": self.bid,
            "ask": self.ask,
            "volume": self.volume,
            "status": "STALE" if self.is_stale else self.status,
            "source": self.source,
            "error": self.error,
            "updated_at": self.updated_at,
            "updated_utc": self.updated_utc,
            "is_stale": self.is_stale,
        }


class DeltaMarketFeed:
    """
    Public market feed with one polling worker per approved symbol.

    UI callbacks receive a MarketSnapshot object. The implementation
    never marks an invalid or missing price as live.
    """

    def __init__(
        self,
        symbols=None,
        poll_interval=POLL_INTERVAL_SECONDS,
        request_timeout=REQUEST_TIMEOUT_SECONDS,
        client=None,
    ):
        requested = symbols or APPROVED_SYMBOLS
        self.symbols = tuple(
            str(symbol).upper().strip()
            for symbol in requested
            if str(symbol).upper().strip() in APPROVED_SYMBOLS
        )

        if not self.symbols:
            self.symbols = tuple(APPROVED_SYMBOLS)

        self.poll_interval = max(2.0, float(poll_interval))
        self.request_timeout = max(1.0, float(request_timeout))

        self.client = client or DeltaPublicClient(
            timeout=int(self.request_timeout)
        )

        self._lock = threading.RLock()
        self._callbacks = []
        self._snapshots = {
            symbol: MarketSnapshot(symbol=symbol)
            for symbol in self.symbols
        }
        self._stop_event = threading.Event()
        self._workers = {}
        self._running = False
        self._generation = 0

    @property
    def running(self):
        with self._lock:
            return self._running

    def add_callback(self, callback: Callable):
        if not callable(callback):
            raise TypeError("Market feed callback must be callable.")

        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

        return callback

    def remove_callback(self, callback: Callable):
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def get_snapshot(self, symbol):
        symbol = str(symbol).upper().strip()

        with self._lock:
            snapshot = self._snapshots.get(symbol)
            if snapshot is None:
                return None
            return self._copy_snapshot(snapshot)

    def get_all_snapshots(self):
        with self._lock:
            return {
                symbol: self._copy_snapshot(snapshot)
                for symbol, snapshot in self._snapshots.items()
            }

    @staticmethod
    def _copy_snapshot(snapshot):
        return MarketSnapshot(
            symbol=snapshot.symbol,
            last_price=snapshot.last_price,
            bid=snapshot.bid,
            ask=snapshot.ask,
            volume=snapshot.volume,
            status=snapshot.status,
            source=snapshot.source,
            error=snapshot.error,
            updated_at=snapshot.updated_at,
            updated_utc=snapshot.updated_utc,
        )

    def start(self, *_):
        """Start once; return immediately without blocking the UI."""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._generation += 1
            generation = self._generation
            self._stop_event.clear()

            for symbol in self.symbols:
                worker = threading.Thread(
                    target=self._poll_symbol,
                    args=(symbol, generation),
                    name=f"GarryMarket-{symbol}",
                    daemon=True,
                )
                self._workers[symbol] = worker
                worker.start()

        logger.info(
            "Market feed started for %d approved symbols.",
            len(self.symbols),
        )

    def stop(self, *_):
        """Request shutdown without waiting on network calls."""
        with self._lock:
            if not self._running:
                return

            self._running = False
            self._generation += 1
            self._stop_event.set()
            self._workers.clear()

        logger.info("Market feed stop requested.")

    def _is_current_generation(self, generation):
        with self._lock:
            return (
                self._running
                and self._generation == generation
                and not self._stop_event.is_set()
            )

    def _poll_symbol(self, symbol, generation):
        while self._is_current_generation(generation):
            try:
                payload = self.client.get_ticker(symbol)
                ticker = self._extract_ticker(payload, symbol)

                price = self._positive_number(
                    ticker,
                    (
                        "close",
                        "last_price",
                        "last_traded_price",
                        "price",
                        "mark_price",
                        "m",
                        "p",
                    ),
                )

                if price is None:
                    raise DeltaAPIError(
                        f"No valid ticker price returned for {symbol}."
                    )

                bid = self._positive_number(
                    ticker,
                    ("best_bid", "bid", "buy", "bp"),
                )
                ask = self._positive_number(
                    ticker,
                    ("best_ask", "ask", "sell", "ap"),
                )
                volume = self._positive_number(
                    ticker,
                    ("volume", "volume_24h", "v"),
                )

                quotes = ticker.get("quotes")
                if isinstance(quotes, dict):
                    bid = bid or self._positive_number(
                        quotes, ("best_bid", "bid", "buy")
                    )
                    ask = ask or self._positive_number(
                        quotes, ("best_ask", "ask", "sell")
                    )

                self._update_market_snapshot(
                    symbol=symbol,
                    price=price,
                    bid=bid,
                    ask=ask,
                    volume=volume,
                    source="REST",
                    generation=generation,
                )

            except Exception as exc:
                if self._is_current_generation(generation):
                    logger.warning(
                        "Ticker request failed for %s: %s: %s",
                        symbol,
                        type(exc).__name__,
                        exc,
                    )
                    self._set_error(
                        symbol,
                        f"{type(exc).__name__}: {exc}",
                        generation,
                    )

            self._stop_event.wait(self.poll_interval)

    @staticmethod
    def _extract_ticker(payload, requested_symbol):
        """
        Delta REST commonly returns:
        {"success": true, "result": {"symbol": "...", "close": "..."}}
        """
        if not isinstance(payload, dict):
            raise DeltaAPIError("Invalid ticker response type.")

        if payload.get("success") is False:
            raise DeltaAPIError("Delta reported ticker request failure.")

        result = payload.get("result", payload.get("data", payload))

        if isinstance(result, list):
            result = next(
                (
                    item for item in result
                    if isinstance(item, dict)
                    and str(
                        item.get("symbol", item.get("s", ""))
                    ).upper() == requested_symbol
                ),
                None,
            )

        if not isinstance(result, dict):
            raise DeltaAPIError("Ticker response has no result object.")

        # Some WebSocket messages wrap ticker details in "d".
        nested = result.get("d")
        if isinstance(nested, dict):
            result = {**result, **nested}

        return result

    @staticmethod
    def _positive_number(mapping, keys):
        if not isinstance(mapping, dict):
            return None

        for key in keys:
            value = mapping.get(key)
            if value is None or isinstance(value, bool):
                continue

            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError):
                continue

            if number > 0:
                return number

        return None

    @staticmethod
    def _utc_now():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def _update_market_snapshot(
        self,
        symbol,
        price,
        bid=None,
        ask=None,
        volume=None,
        source="REST",
        generation=None,
    ):
        try:
            price = float(price)
        except (TypeError, ValueError, OverflowError):
            return

        if price <= 0:
            return

        with self._lock:
            if symbol not in self._snapshots:
                return

            if generation is not None:
                if (
                    not self._running
                    or generation != self._generation
                ):
                    return

            snapshot = self._snapshots[symbol]
            snapshot.last_price = price
            snapshot.bid = bid
            snapshot.ask = ask
            snapshot.volume = volume
            snapshot.status = "CONNECTED"
            snapshot.source = source
            snapshot.error = ""
            snapshot.updated_at = time.time()
            snapshot.updated_utc = self._utc_now()

            published = self._copy_snapshot(snapshot)
            callbacks = list(self._callbacks)

        self._notify_callbacks(callbacks, published)

    def _set_error(self, symbol, message, generation=None):
        with self._lock:
            if symbol not in self._snapshots:
                return

            if generation is not None:
                if (
                    not self._running
                    or generation != self._generation
                ):
                    return

            snapshot = self._snapshots[symbol]
            snapshot.error = str(message)[:500]

            # Keep the last real price for diagnostics, but mark it stale
            # after the freshness threshold; never replace it with zero.
            snapshot.status = (
                "STALE" if snapshot.last_price is not None else "OFFLINE"
            )

            published = self._copy_snapshot(snapshot)
            callbacks = list(self._callbacks)

        self._notify_callbacks(callbacks, published)

    @staticmethod
    def _notify_callbacks(callbacks, snapshot):
        for callback in callbacks:
            try:
                callback(snapshot)
            except Exception:
                logger.exception(
                    "Market feed callback failed for %s.",
                    snapshot.symbol,
                )

    def _extract_symbol(self, item):
        if not isinstance(item, dict):
            return None

        for key in ("symbol", "sy", "s"):
            value = item.get(key)
            if value:
                symbol = str(value).upper().strip()
                if symbol in self.symbols:
                    return symbol

        return None

    def _first_positive(self, item, keys):
        return self._positive_number(item, keys)

    def _to_float(self, value):
        try:
            number = float(value)
            return number if number > 0 else 0.0
        except (TypeError, ValueError, OverflowError):
            return 0.0

    def _handle_ticker_message(self, payload: dict) -> None:
        """
        Parse standard and compact ticker messages for compatibility.
        REST remains the active fallback feed.
        """
        if not isinstance(payload, dict):
            return

        data = payload.get("data", payload.get("result", payload))

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            nested = data.get("d")
            if isinstance(nested, list):
                items = nested
            elif isinstance(nested, dict):
                items = [nested]
            else:
                items = [data]
        else:
            return

        for item in items:
            if not isinstance(item, dict):
                continue

            symbol = self._extract_symbol(item)
            if not symbol:
                symbol = self._extract_symbol(payload)
            if not symbol:
                continue

            nested = item.get("d")
            if isinstance(nested, dict):
                item = {**item, **nested}

            price = self._first_positive(
                item,
                (
                    "close",
                    "last_price",
                    "last_traded_price",
                    "mark_price",
                    "price",
                    "m",
                    "p",
                ),
            )

            if not price:
                ohlc = item.get("ohlc")
                if isinstance(ohlc, dict):
                    price = self._first_positive(
                        ohlc, ("close", "c")
                    )
                elif isinstance(ohlc, (list, tuple)) and len(ohlc) >= 4:
                    price = self._to_float(ohlc[3])

            quotes = item.get("quotes")
            bid = self._first_positive(
                item, ("best_bid", "bid", "bp", "b")
            )
            ask = self._first_positive(
                item, ("best_ask", "ask", "ap", "a")
            )
            volume = self._first_positive(
                item, ("volume", "volume_24h", "v")
            )

            if isinstance(quotes, dict):
                bid = bid or self._first_positive(
                    quotes, ("best_bid", "bid", "buy")
                )
                ask = ask or self._first_positive(
                    quotes, ("best_ask", "ask", "sell")
                )
            elif isinstance(quotes, (list, tuple)):
                if len(quotes) >= 2:
                    bid = bid or self._to_float(quotes[0])
                    ask = ask or self._to_float(quotes[1])

            if price:
                self._update_market_snapshot(
                    symbol=symbol,
                    price=price,
                    bid=bid,
                    ask=ask,
                    volume=volume,
                    source="WEBSOCKET",
                )
