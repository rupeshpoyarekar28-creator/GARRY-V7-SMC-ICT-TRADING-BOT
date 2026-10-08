"""
GARRY V7 SMC ICT TRADING BOT

STEP 5 - Delta WebSocket Live Market Feed

Purpose:
- Delta Exchange India public WebSocket
- Locked 7 trading pairs only
- WebSocket primary market data
- REST fallback
- Automatic reconnect
- Stale-data protection
- Thread-safe snapshots
- Callback support
- Health monitoring

IMPORTANT:
- Public market data only
- No API key
- No API secret
- No private authentication
- No order placement
- No real trading

Locked symbols:
    BTCUSD
    XAUTUSD
    ETHUSD
    PAXGUSD
    SOLUSD
    XRPUSD
    UNIUSD
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


# ================================================================
# DELTA WEBSOCKET
# ================================================================

DELTA_PUBLIC_WS_URL = (
    "wss://public-socket.india.delta.exchange"
)

# WebSocket reconnect configuration
WS_RECONNECT_INITIAL = 2.0
WS_RECONNECT_MAX = 30.0

# REST fallback
DEFAULT_REST_INTERVAL = 5.0

# Market-data stale protection
DEFAULT_STALE_AFTER = 15.0

# WebSocket timeout
WS_PING_INTERVAL = 20.0
WS_PING_TIMEOUT = 10.0


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
    Delta public market-data engine.

    Primary:
        WebSocket

    Fallback:
        REST polling

    The engine never places orders.
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
        # Only allow the locked approved symbols.
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

        self._ws_thread: Optional[
            threading.Thread
        ] = None

        self._rest_thread: Optional[
            threading.Thread
        ] = None

        self._ws: Optional[
            websocket.WebSocketApp
        ] = None

        self._stop_event = threading.Event()

        self._ws_connected = False
        self._rest_fallback_active = False

        self._last_error = ""
        self._connection_status = "DISCONNECTED"

        self._reconnect_delay = (
            WS_RECONNECT_INITIAL
        )

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

        with self._lock:

            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def remove_callback(
        self,
        callback: Callable[
            [MarketSnapshot],
            None,
        ],
    ) -> None:

        with self._lock:

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
    # START
    # ============================================================

    def start(self) -> None:

        with self._lock:

            if self._running:
                return

            self._running = True

        self._stop_event.clear()

        self._set_connection_status(
            "CONNECTING"
        )

        # --------------------------------------------------------
        # WebSocket primary thread
        # --------------------------------------------------------

        self._ws_thread = threading.Thread(
            target=self._websocket_loop,
            name="GARRY-V7-WebSocket",
            daemon=True,
        )

        self._ws_thread.start()

        # --------------------------------------------------------
        # REST fallback thread
        #
        # REST remains available as a safety fallback.
        # --------------------------------------------------------

        self._rest_thread = threading.Thread(
            target=self._rest_loop,
            name="GARRY-V7-REST-Fallback",
            daemon=True,
        )

        self._rest_thread.start()

    # ============================================================
    # STOP
    # ============================================================

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

        ws_thread = self._ws_thread

        if (
            ws_thread is not None
            and ws_thread.is_alive()
            and ws_thread is not current
        ):

            ws_thread.join(
                timeout=3.0
            )

        rest_thread = self._rest_thread

        if (
            rest_thread is not None
            and rest_thread.is_alive()
            and rest_thread is not current
        ):

            rest_thread.join(
                timeout=3.0
            )

        self._ws_thread = None
        self._rest_thread = None
        self._ws = None

        self._ws_connected = False
        self._rest_fallback_active = False

        self._set_connection_status(
            "DISCONNECTED"
        )

    # ============================================================
    # WEBSOCKET LOOP
    # ============================================================

    def _websocket_loop(self) -> None:

        while (
            self._running
            and not self._stop_event.is_set()
        ):

            try:

                self._set_connection_status(
                    "WS_CONNECTING"
                )

                self._connect_websocket()

                # If run_forever returns normally,
                # reconnect after a short delay.

                if self._running:

                    self._set_connection_status(
                        "WS_RECONNECTING"
                    )

                    self._wait_for_reconnect()

            except Exception as exc:

                self._ws_connected = False

                self._set_connection_status(
                    "WS_ERROR",
                    str(exc),
                )

                self._wait_for_reconnect()

    # ============================================================
    # WEBSOCKET CONNECTION
    # ============================================================

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

    # ============================================================
    # WEBSOCKET OPEN
    # ============================================================

    def _on_ws_open(
        self,
        ws,
    ) -> None:

        self._ws_connected = True
        self._rest_fallback_active = False

        self._reconnect_delay = (
            WS_RECONNECT_INITIAL
        )

        self._set_connection_status(
            "WS_CONNECTED"
        )

        self._subscribe_channels(ws)

    # ============================================================
    # SUBSCRIBE
    # ============================================================

    def _subscribe_channels(
        self,
        ws,
    ) -> None:

        symbols = list(
            self.symbols
        )

        # --------------------------------------------------------
        # Ticker channel
        # --------------------------------------------------------

        ticker_message = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": "ticker",
                        "symbols": symbols,
                    }
                ]
            },
        }

        self._send_json(
            ws,
            ticker_message,
        )

        # --------------------------------------------------------
        # L1 order book channel
        # --------------------------------------------------------

        ob_message = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": "ob_l1",
                        "symbols": symbols,
                    }
                ]
            },
        }

        self._send_json(
            ws,
            ob_message,
        )

        # --------------------------------------------------------
        # 5 minute candle channel
        # --------------------------------------------------------

        candle_message = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": "candlestick_5m",
                        "symbols": symbols,
                    }
                ]
            },
        }

        self._send_json(
            ws,
            candle_message,
        )

        # --------------------------------------------------------
        # System status
        # --------------------------------------------------------

        system_message = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": "system_status",
                        "symbols": [],
                    }
                ]
            },
        }

        self._send_json(
            ws,
            system_message,
        )

    # ============================================================
    # SEND JSON
    # ============================================================

    @staticmethod
    def _send_json(
        ws,
        payload: dict,
    ) -> None:

        ws.send(
            json.dumps(payload)
        )

    # ============================================================
    # WEBSOCKET MESSAGE
    # ============================================================

    def _on_ws_message(
        self,
        ws,
        message: str,
    ) -> None:

        try:

            payload = json.loads(
                message
            )

        except (
            json.JSONDecodeError,
            TypeError,
        ):

            return

        if not isinstance(
            payload,
            dict,
        ):
            return

        message_type = str(
            payload.get(
                "type",
                ""
            )
        ).lower()

        # --------------------------------------------------------
        # Subscription / heartbeat / system messages
        # --------------------------------------------------------

        if message_type in {
            "subscriptions",
            "heartbeat",
            "system_status",
            "success",
            "error",
        }:

            if message_type == "error":

                error = str(
                    payload.get(
                        "message",
                        "WebSocket error",
                    )
                )

                self._set_connection_status(
                    "WS_ERROR",
                    error,
                )

            return

        # --------------------------------------------------------
        # Extract channel
        # --------------------------------------------------------

        channel = str(
            payload.get(
                "channel",
                ""
            )
        ).lower()

        if channel == "ticker":

            self._handle_ticker_message(
                payload
            )

        elif channel == "ob_l1":

            self._handle_orderbook_message(
                payload
            )

        elif channel.startswith(
            "candlestick_"
        ):

            # Candle data is intentionally
            # not written into ticker price.
            #
            # SMC/ICT candle engine can use
            # a separate candle stream later.

            return

        # --------------------------------------------------------
        # Some Delta messages may expose
        # symbol at top-level.
        # --------------------------------------------------------

        elif payload.get(
            "symbol"
        ):

            self._handle_generic_market_message(
                payload
            )

        self._refresh_stale_states()

    # ============================================================
    # TICKER MESSAGE
    # ============================================================

    def _handle_ticker_message(
        self,
        payload: dict,
    ) -> None:

        data = payload.get(
            "data",
            payload.get(
                "result",
                payload,
            ),
        )

        if not isinstance(
            data,
            dict,
        ):
            return

        symbol = self._extract_symbol(
            data
        )

        if symbol is None:

            symbol = self._extract_symbol(
                payload
            )

        if symbol is None:
            return

        if symbol not in self.symbols:
            return

        price = self._to_float(
            data.get("close")
        )

        if price <= 0:

            price = self._to_float(
                data.get("mark_price")
            )

        if price <= 0:

            price = self._to_float(
                data.get("last_traded_price")
            )

        if price <= 0:
            return

        bid = self._to_float(
            data.get("best_bid")
        )

        ask = self._to_float(
            data.get("best_ask")
        )

        volume = self._to_float(
            data.get("volume")
        )

        self._update_market_snapshot(
            symbol=symbol,
            price=price,
            bid=bid,
            ask=ask,
            volume=volume,
            source="WEBSOCKET",
        )

    # ============================================================
    # ORDER BOOK L1
    # ============================================================

    def _handle_orderbook_message(
        self,
        payload: dict,
    ) -> None:

        data = payload.get(
            "data",
            payload.get(
                "result",
                payload,
            ),
        )

        if not isinstance(
            data,
            dict,
        ):
            return

        symbol = self._extract_symbol(
            data
        )

        if symbol is None:

            symbol = self._extract_symbol(
                payload
            )

        if symbol is None:
            return

        if symbol not in self.symbols:
            return

        bid = self._to_float(
            data.get("best_bid")
        )

        ask = self._to_float(
            data.get("best_ask")
        )

        if bid <= 0:

            bid = self._to_float(
                data.get("bid")
            )

        if ask <= 0:

            ask = self._to_float(
                data.get("ask")
            )

        with self._lock:

            current = self._snapshots.get(
                symbol
            )

            if current is None:
                return

            price = current.price
            volume = current.volume

        if price <= 0:
            return

        self._update_market_snapshot(
            symbol=symbol,
            price=price,
            bid=bid,
            ask=ask,
            volume=volume,
            source="WEBSOCKET",
        )

    # ============================================================
    # GENERIC MARKET MESSAGE
    # ============================================================

    def _handle_generic_market_message(
        self,
        payload: dict,
    ) -> None:

        symbol = self._extract_symbol(
            payload
        )

        if symbol is None:
            return

        if symbol not in self.symbols:
            return

        price = self._to_float(
            payload.get("close")
        )

        if price <= 0:

            price = self._to_float(
                payload.get(
                    "mark_price"
                )
            )

        if price <= 0:
            return

        self._update_market_snapshot(
            symbol=symbol,
            price=price,
            source="WEBSOCKET",
        )

    # ============================================================
    # UPDATE SNAPSHOT
    # ============================================================

    def _update_market_snapshot(
        self,
        symbol: str,
        price: float,
        bid: float = 0.0,
        ask: float = 0.0,
        volume: float = 0.0,
        source: str = "WEBSOCKET",
    ) -> None:

        callbacks: list[
            Callable[[MarketSnapshot], None]
        ]

        with self._lock:

            current = self._snapshots.get(
                symbol
            )

            if current is None:
                return

            if price <= 0:
                price = current.price

            if bid <= 0:
                bid = current.bid

            if ask <= 0:
                ask = current.ask

            if volume <= 0:
                volume = current.volume

            snapshot = MarketSnapshot(
                symbol=symbol,
                price=price,
                bid=bid,
                ask=ask,
                volume=volume,
                timestamp=time.time(),
                status="LIVE",
                source=source,
                error="",
            )

            self._snapshots[
                symbol
            ] = snapshot

            callbacks = list(
                self._callbacks
            )

        # --------------------------------------------------------
        # Callback outside lock.
        # --------------------------------------------------------

        for callback in callbacks:

            try:

                callback(
                    snapshot
                )

            except Exception:

                # A UI/strategy callback must
                # never kill market feed.
                continue

    # ============================================================
    # REST FALLBACK LOOP
    # ============================================================

    def _rest_loop(self) -> None:

        while (
            self._running
            and not self._stop_event.is_set()
        ):

            try:

                # ------------------------------------------------
                # REST is used when WebSocket is not healthy.
                # ------------------------------------------------

                if not self._ws_connected:

                    self._rest_fallback_active = True

                    self._poll_all_symbols()

                else:

                    self._rest_fallback_active = False

                    self._refresh_stale_states()

            except Exception as exc:

                self._set_connection_status(
                    "REST_ERROR",
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

                snapshot = self._parse_rest_ticker(
                    symbol,
                    ticker,
                )

                self._update_market_snapshot(
                    symbol=snapshot.symbol,
                    price=snapshot.price,
                    bid=snapshot.bid,
                    ask=snapshot.ask,
                    volume=snapshot.volume,
                    source="REST",
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

            if not self._ws_connected:

                self._set_connection_status(
                    "REST_FALLBACK"
                )

        else:

            if not self._ws_connected:

                self._set_connection_status(
                    "OFFLINE",
                    "No market data received",
                )

        self._refresh_stale_states()

    # ============================================================
    # REST TICKER PARSER
    # ============================================================

    def _parse_rest_ticker(
        self,
        symbol: str,
        payload: dict,
    ) -> MarketSnapshot:

        if not isinstance(
            payload,
            dict,
        ):

            raise ValueError(
                "Invalid ticker payload"
            )

        ticker = payload.get(
            "result",
            payload,
        )

        if not isinstance(
            ticker,
            dict,
        ):

            raise ValueError(
                "Invalid ticker result"
            )

        price = self._to_float(
            ticker.get("close")
        )

        if price <= 0:

            price = self._to_float(
                ticker.get(
                    "mark_price"
                )
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
            quotes.get(
                "best_bid"
            )
        )

        if bid <= 0:

            bid = self._to_float(
                ticker.get(
                    "best_bid"
                )
            )

        ask = self._to_float(
            quotes.get(
                "best_ask"
            )
        )

        if ask <= 0:

            ask = self._to_float(
                ticker.get(
                    "best_ask"
                )
            )

        volume = self._to_float(
            ticker.get(
                "volume"
            )
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

            snapshot.error = error

            # Do not overwrite an otherwise
            # fresh WebSocket snapshot.
            if snapshot.timestamp <= 0:

                snapshot.status = "ERROR"

    # ============================================================
    # STALE DATA
    # ============================================================

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
    # RECONNECT
    # ============================================================

    def _wait_for_reconnect(self) -> None:

        delay = min(
            self._reconnect_delay,
            WS_RECONNECT_MAX,
        )

        self._stop_event.wait(
            delay
        )

        self._reconnect_delay = min(
            self._reconnect_delay * 2.0,
            WS_RECONNECT_MAX,
        )

    # ============================================================
    # WEBSOCKET EVENTS
    # ============================================================

    def _on_ws_error(
        self,
        ws,
        error,
    ) -> None:

        self._ws_connected = False

        self._set_connection_status(
            "WS_ERROR",
            str(error),
        )

    def _on_ws_close(
        self,
        ws,
        close_status_code,
        close_msg,
    ) -> None:

        self._ws_connected = False

        if self._running:

            self._set_connection_status(
                "WS_DISCONNECTED",
                str(close_msg or ""),
            )

        else:

            self._set_connection_status(
                "DISCONNECTED"
            )

    # ============================================================
    # SYMBOL EXTRACTION
    # ============================================================

    @staticmethod
    def _extract_symbol(
        data: dict,
    ) -> Optional[str]:

        possible_keys = (
            "symbol",
            "product_symbol",
            "instrument",
        )

        for key in possible_keys:

            value = data.get(
                key
            )

            if value is None:
                continue

            symbol = str(
                value
            ).upper().strip()

            if symbol:
                return symbol

        return None

    # ============================================================
    # NUMBER CONVERSION
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
            "websocket_connected": (
                self._ws_connected
            ),
            "rest_fallback": (
                self._rest_fallback_active
            ),
            "symbols": len(
                self.symbols
            ),
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
