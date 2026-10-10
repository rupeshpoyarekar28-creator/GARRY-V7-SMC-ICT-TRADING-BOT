"""
GARRY V7 SMC ICT TRADING BOT
Delta Exchange India public market feed.
Public data only. No credentials. No order placement.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
from dataclasses import dataclass
from typing import Callable, Optional

import websocket

from data.delta_public import (
    APPROVED_SYMBOLS,
    DeltaAPIError,
    DeltaPublicClient,
)

DELTA_PUBLIC_WS_URL = "wss://public-socket.india.delta.exchange"
WS_RECONNECT_INITIAL = 2.0
WS_RECONNECT_MAX = 30.0
DEFAULT_REST_INTERVAL = 5.0
DEFAULT_STALE_AFTER = 15.0
WS_PING_INTERVAL = 20.0
WS_PING_TIMEOUT = 10.0


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
    def is_stale(self, stale_after: float = DEFAULT_STALE_AFTER) -> bool:
        return self.timestamp <= 0 or time.time() - self.timestamp > stale_after


class DeltaMarketFeed:
    """Public WebSocket market feed with REST fallback."""

    def __init__(
        self,
        symbols: Optional[tuple[str, ...]] = None,
        rest_interval: float = DEFAULT_REST_INTERVAL,
        stale_after: float = DEFAULT_STALE_AFTER,
    ):
        requested = symbols if symbols is not None else APPROVED_SYMBOLS
        self.symbols = tuple(
            str(s).upper().strip()
            for s in requested
            if str(s).upper().strip() in APPROVED_SYMBOLS
        )

        self.rest_interval = max(2.0, float(rest_interval))
        self.stale_after = max(5.0, float(stale_after))
        self.client = DeltaPublicClient()

        self._snapshots = {
            symbol: MarketSnapshot(symbol=symbol)
            for symbol in self.symbols
        }
        self._callbacks: list[Callable[[MarketSnapshot], None]] = []
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._running = False
        self._ws_connected = False
        self._rest_fallback_active = False
        self._last_error = ""
        self._connection_status = "DISCONNECTED"
        self._reconnect_delay = WS_RECONNECT_INITIAL
        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._rest_thread: Optional[threading.Thread] = None

    def add_callback(self, callback: Callable[[MarketSnapshot], None]) -> None:
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[MarketSnapshot], None]) -> None:
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def get_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        with self._lock:
            item = self._snapshots.get(str(symbol).upper().strip())
            if item is None:
                return None
            return MarketSnapshot(
                symbol=item.symbol,
                price=item.price,
                bid=item.bid,
                ask=item.ask,
                volume=item.volume,
                timestamp=item.timestamp,
                status=item.status,
                source=item.source,
                error=item.error,
            )

    def get_all_snapshots(self) -> dict[str, MarketSnapshot]:
        with self._lock:
            return {
                symbol: MarketSnapshot(
                    symbol=item.symbol,
                    price=item.price,
                    bid=item.bid,
                    ask=item.ask,
                    volume=item.volume,
                    timestamp=item.timestamp,
                    status=item.status,
                    source=item.source,
                    error=item.error,
                )
                for symbol, item in self._snapshots.items()
            }

    @property
    def connection_status(self) -> str:
        with self._lock:
            return self._connection_status

    @property
    def last_error(self) -> str:
        with self._lock:
            return self._last_error

    def _set_connection_status(self, status: str, error: str = "") -> None:
        with self._lock:
            self._connection_status = status
            self._last_error = error

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True

        self._stop_event.clear()
        self._set_connection_status("CONNECTING")

        self._ws_thread = threading.Thread(
            target=self._websocket_loop,
            name="GARRY-V7-WebSocket",
            daemon=True,
        )
        self._rest_thread = threading.Thread(
            target=self._rest_loop,
            name="GARRY-V7-REST-Fallback",
            daemon=True,
        )
        self._ws_thread.start()
        self._rest_thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False

        self._stop_event.set()
        ws = self._ws

        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

        current = threading.current_thread()
        for thread in (self._ws_thread, self._rest_thread):
            if thread is not None and thread.is_alive() and thread is not current:
                thread.join(timeout=3.0)

        self._ws = None
        self._ws_thread = None
        self._rest_thread = None
        self._ws_connected = False
        self._rest_fallback_active = False
        self._set_connection_status("DISCONNECTED")

    def _websocket_loop(self) -> None:
        while self._running and not self._stop_event.is_set():
            try:
                self._set_connection_status("WS_CONNECTING")
                self._connect_websocket()
                if self._running:
                    self._set_connection_status("WS_RECONNECTING")
                    self._wait_for_reconnect()
            except Exception as exc:
                self._ws_connected = False
                self._set_connection_status("WS_ERROR", str(exc))
                self._wait_for_reconnect()

    def _connect_websocket(self) -> None:
        self._ws = websocket.WebSocketApp(
            DELTA_PUBLIC_WS_URL,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close,
        )
        self._ws.run_forever(
            ping_interval=WS_PING_INTERVAL,
            ping_timeout=WS_PING_TIMEOUT,
        )

    def _on_ws_open(self, ws) -> None:
        self._ws_connected = True
        self._reconnect_delay = WS_RECONNECT_INITIAL
        self._set_connection_status("WS_CONNECTED")
        self._subscribe_channels(ws)

    def _subscribe_channels(self, ws) -> None:
        for channel in ("ticker", "ob_l1", "candlestick_5m"):
            self._send_json(ws, {
                "type": "subscribe",
                "payload": {
                    "channels": [{
                        "name": channel,
                        "symbols": list(self.symbols),
                    }]
                },
            })

        self._send_json(ws, {
            "type": "subscribe",
            "payload": {
                "channels": [{"name": "system_status", "symbols": []}]
            },
        })

    @staticmethod
    def _send_json(ws, payload: dict) -> None:
        ws.send(json.dumps(payload))

    def _on_ws_message(self, ws, message: str) -> None:
        try:
            payload = json.loads(message)
        except (json.JSONDecodeError, TypeError):
            return

        if not isinstance(payload, dict):
            return

        message_type = str(payload.get("type", "")).lower()
        if message_type in {
            "subscriptions", "heartbeat", "system_status", "success", "error"
        }:
            if message_type == "error":
                self._set_connection_status(
                    "WS_ERROR",
                    str(payload.get("message", "WebSocket error")),
                )
            return

        channel = str(payload.get("channel", "")).lower()

        if channel == "ticker" or message_type == "ticker":
            self._handle_ticker_message(payload)
        elif channel == "ob_l1":
            self._handle_orderbook_message(payload)
        elif channel.startswith("candlestick_"):
            return
        elif payload.get("symbol") or payload.get("sy"):
            self._handle_generic_market_message(payload)

        self._refresh_stale_states()

    def _handle_ticker_message(self, payload: dict) -> None:
        data = payload.get("data", payload.get("result", payload))
        if not isinstance(data, dict):
            data = payload

        symbol = self._extract_symbol(data) or self._extract_symbol(payload)
        if symbol not in self.symbols:
            return

        nested = data.get("d")
        price = self._first_positive(
            data,
            ("close", "mark_price", "last_traded_price", "last_price", "price", "sp"),
        )

        if price <= 0 and isinstance(nested, dict):
            price = self._first_positive(
                nested,
                ("close", "mark_price", "last_traded_price", "last_price", "price", "sp", "p"),
            )

        if price <= 0:
            return

        bid = self._first_positive(data, ("best_bid", "bid", "bp"))
        ask = self._first_positive(data, ("best_ask", "ask", "ap"))
        volume = self._first_positive(data, ("volume", "v"))

        if isinstance(nested, dict):
            bid = bid or self._first_positive(nested, ("best_bid", "bid", "bp"))
            ask = ask or self._first_positive(nested, ("best_ask", "ask", "ap"))
            volume = volume or self._first_positive(nested, ("volume", "v"))

        self._update_market_snapshot(
            symbol, price, bid, ask, volume, "WEBSOCKET"
        )

    def _handle_orderbook_message(self, payload: dict) -> None:
        data = payload.get("data", payload.get("result", payload))
        if not isinstance(data, dict):
            return

        symbol = self._extract_symbol(data) or self._extract_symbol(payload)
        if symbol not in self.symbols:
            return

        bid = self._first_positive(data, ("best_bid", "bid", "bp"))
        ask = self._first_positive(data, ("best_ask", "ask", "ap"))

        with self._lock:
            current = self._snapshots.get(symbol)
            if current is None or current.price <= 0:
                return
            price, volume = current.price, current.volume

        self._update_market_snapshot(
            symbol, price, bid, ask, volume, "WEBSOCKET"
        )

    def _handle_generic_market_message(self, payload: dict) -> None:
        symbol = self._extract_symbol(payload)
        if symbol not in self.symbols:
            return

        price = self._first_positive(
            payload, ("close", "mark_price", "last_traded_price", "last_price", "price", "sp")
        )
        if price > 0:
            self._update_market_snapshot(symbol, price, source="WEBSOCKET")

    def _update_market_snapshot(
        self,
        symbol: str,
        price: float,
        bid: float = 0.0,
        ask: float = 0.0,
        volume: float = 0.0,
        source: str = "WEBSOCKET",
    ) -> None:
        if price <= 0:
            return

        with self._lock:
            current = self._snapshots.get(symbol)
            if current is None:
                return

            snapshot = MarketSnapshot(
                symbol=symbol,
                price=price,
                bid=bid if bid > 0 else current.bid,
                ask=ask if ask > 0 else current.ask,
                volume=volume if volume > 0 else current.volume,
                timestamp=time.time(),
                status="LIVE",
                source=source,
                error="",
            )
            self._snapshots[symbol] = snapshot
            callbacks = list(self._callbacks)

        for callback in callbacks:
            try:
                callback(snapshot)
            except Exception:
                continue

    def _rest_loop(self) -> None:
        while self._running and not self._stop_event.is_set():
            try:
                snapshots = self.get_all_snapshots()
                needs_fallback = any(
                    item.price <= 0 or item.is_stale(self.stale_after)
                    for item in snapshots.values()
                )

                if not self._ws_connected or needs_fallback:
                    self._rest_fallback_active = True
                    self._poll_all_symbols()
                else:
                    self._rest_fallback_active = False
                    self._refresh_stale_states()
            except Exception as exc:
                self._set_connection_status("REST_ERROR", str(exc))

            self._stop_event.wait(self.rest_interval)

    def _poll_all_symbols(self) -> None:
        successful_updates = 0

        for symbol in self.symbols:
            if not self._running or self._stop_event.is_set():
                break

            try:
                ticker = self.client.get_ticker(symbol)
                snapshot = self._parse_rest_ticker(symbol, ticker)
                self._update_market_snapshot(
                    snapshot.symbol,
                    snapshot.price,
                    snapshot.bid,
                    snapshot.ask,
                    snapshot.volume,
                    "REST",
                )
                successful_updates += 1

            except (
                DeltaAPIError,
                urllib.error.URLError,
                TimeoutError,
                ValueError,
                TypeError,
            ) as exc:
                self._mark_error(symbol, str(exc))

        if successful_updates:
            if not self._ws_connected:
                self._set_connection_status("REST_FALLBACK")
        elif not self._ws_connected:
            self._set_connection_status("OFFLINE", "No market data received")

        self._refresh_stale_states()

    def _parse_rest_ticker(self, symbol: str, payload: dict) -> MarketSnapshot:
        if not isinstance(payload, dict):
            raise ValueError("Invalid ticker payload")

        ticker = payload.get("result", payload)
        if not isinstance(ticker, dict):
            raise ValueError("Invalid ticker result")

        price = self._first_positive(ticker, (
            "close", "mark_price", "last_traded_price", "last_price", "price"
        ))

        quotes = ticker.get("quotes")
        if not isinstance(quotes, dict):
            quotes = {}

        bid = self._first_positive(quotes, ("best_bid", "bid"))
        bid = bid or self._first_positive(ticker, ("best_bid", "bid"))
        ask = self._first_positive(quotes, ("best_ask", "ask"))
        ask = ask or self._first_positive(ticker, ("best_ask", "ask"))
        volume = self._first_positive(ticker, ("volume",))

        if price <= 0:
            raise ValueError("Invalid market price")

        return MarketSnapshot(
            symbol=symbol,
            price=price,
            bid=bid,
            ask=ask,
            volume=volume,
            timestamp=time.time(),
            status="LIVE",
            source="REST",
        )

    def _mark_error(self, symbol: str, error: str) -> None:
        with self._lock:
            snapshot = self._snapshots.get(symbol)
            if snapshot is None:
                return
            snapshot.error = error
            if snapshot.timestamp <= 0:
                snapshot.status = "ERROR"

    def _refresh_stale_states(self) -> None:
        with self._lock:
            for snapshot in self._snapshots.values():
                if snapshot.is_stale(self.stale_after) and snapshot.timestamp > 0:
                    snapshot.status = "STALE"

    def _wait_for_reconnect(self) -> None:
        delay = min(self._reconnect_delay, WS_RECONNECT_MAX)
        self._stop_event.wait(delay)
        self._reconnect_delay = min(
            self._reconnect_delay * 2.0, WS_RECONNECT_MAX
        )

    def _on_ws_error(self, ws, error) -> None:
        self._ws_connected = False
        self._set_connection_status("WS_ERROR", str(error))

    def _on_ws_close(self, ws, close_status_code, close_msg) -> None:
        self._ws_connected = False
        self._set_connection_status(
            "WS_DISCONNECTED" if self._running else "DISCONNECTED",
            str(close_msg or "") if self._running else "",
        )

    @staticmethod
    def _extract_symbol(data: dict) -> Optional[str]:
        for key in ("symbol", "product_symbol", "instrument", "sy"):
            value = data.get(key)
            if value is not None:
                symbol = str(value).upper().strip()
                if symbol:
                    return symbol
        return None

    @staticmethod
    def _to_float(value) -> float:
        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _first_positive(cls, data: dict, keys: tuple[str, ...]) -> float:
        for key in keys:
            value = cls._to_float(data.get(key))
            if value > 0:
                return value
        return 0.0

    def health(self) -> dict:
        snapshots = self.get_all_snapshots()
        return {
            "connection": self.connection_status,
            "websocket_connected": self._ws_connected,
            "rest_fallback": self._rest_fallback_active,
            "symbols": len(self.symbols),
            "live": sum(1 for s in snapshots.values() if s.status == "LIVE"),
            "stale": sum(1 for s in snapshots.values() if s.status == "STALE"),
            "errors": sum(1 for s in snapshots.values() if s.status == "ERROR"),
            "last_error": self.last_error,
        }


def create_market_feed(
    callback: Optional[Callable[[MarketSnapshot], None]] = None,
) -> DeltaMarketFeed:
    feed = DeltaMarketFeed(
        symbols=APPROVED_SYMBOLS,
        rest_interval=DEFAULT_REST_INTERVAL,
        stale_after=DEFAULT_STALE_AFTER,
    )
    if callback is not None:
        feed.add_callback(callback)
    return feed
