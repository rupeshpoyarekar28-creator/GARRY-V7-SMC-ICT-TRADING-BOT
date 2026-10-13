
"""
GARRY V7 — Delta Exchange India public market feed.

Features:
- REST polling for approved symbols.
- Thread-safe snapshots and callbacks.
- Independent stop event for each feed generation.
- Bounded exponential retry after request failures.
- Freshness tracking and honest OFFLINE / STALE states.
- No API credentials and no order placement.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
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
RETRY_INITIAL_SECONDS = 2.0
RETRY_MAX_SECONDS = 30.0


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
        return (
            self.updated_at <= 0
            or time.time() - self.updated_at > STALE_AFTER_SECONDS
        )

    def as_dict(self):
        stale = self.is_stale
        status = "STALE" if stale and self.last_price is not None else self.status

        if self.last_price is None:
            status = "OFFLINE" if self.status != "ERROR" else "ERROR"

        return {
            "symbol": self.symbol,
            "last_price": self.last_price,
            "price": self.last_price,
            "bid": self.bid,
            "ask": self.ask,
            "volume": self.volume,
            "status": status,
            "source": self.source,
            "error": self.error,
            "updated_at": self.updated_at,
            "updated_utc": self.updated_utc,
            "is_stale": stale,
        }


class DeltaMarketFeed:
    """Public REST market feed with thread-safe snapshot delivery."""

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
            timeout=max(1, int(self.request_timeout))
        )

        self._lock = threading.RLock()
        self._callbacks = []
        self._snapshots = {
            symbol: MarketSnapshot(symbol=symbol)
            for symbol in self.symbols
        }

        # Each run gets its own event. An old worker can never wait on
        # a newly cleared event after a retry/restart.
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
            return self._copy_snapshot(snapshot) if snapshot else None

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
        """Start one worker per approved symbol without blocking the UI."""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._generation += 1
            generation = self._generation

            stop_event = threading.Event()
            self._stop_event = stop_event
            self._workers = {}

            for symbol in self.symbols:
                worker = threading.Thread(
                    target=self._poll_symbol,
                    args=(symbol, generation, stop_event),
                    name=f"GarryMarket-{symbol}-{generation}",
                    daemon=True,
                )
                self._workers[symbol] = worker
                worker.start()

        logger.info(
            "Market feed started for %d approved symbols.",
            len(self.symbols),
        )

    def stop(self, *_):
        """Signal all workers in the current generation to stop."""
        with self._lock:
            if not self._running:
                return

            self._running = False
            self._generation += 1
            stop_event = self._stop_event
            stop_event.set()
            self._workers = {}

        logger.info("Market feed stop requested.")

    def _is_current_generation(self, generation, stop_event):
        with self._lock:
            return (
                self._running
                and self._generation == generation
                and self._stop_event is stop_event
                and not stop_event.is_set()
            )

    def _poll_symbol(self, symbol, generation, stop_event):
        failures = 0

        while self._is_current_generation(generation, stop_event):
            try:
                payload = self.client.get_ticker(symbol)
                ticker = self._extract_ticker(payload, symbol)

                returned_symbol = ticker.get("symbol", ticker.get("s"))
                if returned_symbol:
                    if str(returned_symbol).upper().strip() != symbol:
                        raise DeltaAPIError(
                            f"Ticker symbol mismatch for {symbol}."
                        )

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
                    ticker, ("best_bid", "bid", "buy", "bp")
                )
                ask = self._positive_number(
                    ticker, ("best_ask", "ask", "sell", "ap")
                )
                volume = self._positive_number(
                    ticker, ("volume", "volume_24h", "v")
                )

                quotes = ticker.get("quotes")
                if isinstance(quotes, dict):
                    bid = bid or self._positive_number(
                        quotes, ("best_bid", "bid", "buy")
                    )
                    ask = ask or self._positive_number(
                        quotes, ("best_ask", "ask", "sell")
                    )

                if not self._is_current_generation(generation, stop_event):
                    break

                self._update_market_snapshot(
                    symbol=symbol,
                    price=price,
                    bid=bid,
                    ask=ask,
                    volume=volume,
                    source="REST",
                    generation=generation,
                    stop_event=stop_event,
                )

                failures = 0
                delay = self.poll_interval

            except Exception as exc:
                if not self._is_current_generation(generation, stop_event):
                    break

                failures += 1
                delay = min(
                    RETRY_MAX_SECONDS,
                    RETRY_INITIAL_SECONDS
                    * (2 ** min(failures - 1, 4)),
                )

                logger.warning(
                    "Ticker request failed for %s (%s): %s",
                    symbol,
                    type(exc).__name__,
                    str(exc)[:250],
                )

                self._set_error(
                    symbol,
                    f"{type(exc).__name__}: {str(exc)[:250]}",
                    generation=generation,
                    stop_event=stop_event,
                )

            if stop_event.wait(delay):
                break

    @staticmethod
    def _extract_ticker(payload, requested_symbol):
        """Extract a ticker from Delta REST response formats."""
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
                    ).upper().strip() == requested_symbol
                ),
                None,
            )

        if not isinstance(result, dict):
            raise DeltaAPIError("Ticker response has no result object.")

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
        stop_event=None,
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
                    or stop_event is not self._stop_event
                    or stop_event.is_set()
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

    def _set_error(
        self,
        symbol,
        message,
        generation=None,
        stop_event=None,
    ):
        with self._lock:
            if symbol not in self._snapshots:
                return

            if generation is not None:
                if (
                    not self._running
                    or generation != self._generation
                    or stop_event is not self._stop_event
                    or stop_event.is_set()
                ):
                    return

            snapshot = self._snapshots[symbol]
            snapshot.error = str(message)[:500]

            if snapshot.last_price is None:
                snapshot.status = "ERROR"
            else:
                snapshot.status = (
                    "STALE"
                    if time.time() - snapshot.updated_at > STALE_AFTER_SECONDS
                    else "CONNECTED"
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
        Parse ticker messages for compatibility.
        REST polling remains the active feed.
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

            nested = item.get("d")
            if isinstance(nested, dict):
                item = {**item, **nested}

            symbol = self._extract_symbol(item)
            if not symbol:
                symbol = self._extract_symbol(payload)
            if not symbol:
                continue

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
            elif isinstance(quotes, (list, tuple)) and len(quotes) >= 2:
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
l
