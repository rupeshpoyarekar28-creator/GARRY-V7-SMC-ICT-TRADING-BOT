"""
GARRY V7 — AUTOMATIC PAPER TRADING ENGINE

Public Delta market data only.
No authentication and no live order execution.

Safety:
- validates OHLC candles
- validates candle timestamps and freshness
- refuses analysis/trades on stale or future-dated market data
- processes each candle at most once
"""

import time
from datetime import datetime, timezone

from data.delta_public import DeltaPublicClient, DeltaAPIError
from data.models import Candle
from strategy.market_structure import analyze_market_structure
from strategy.smc import analyze_smc
from strategy.ict import analyze_ict
from strategy.signals import generate_signal
from strategy.paper_trading import PaperTrader


DEFAULT_RESOLUTION = "5m"
RESOLUTION_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "1d": 86400,
}
# Allow one candle interval plus a small clock/network tolerance.
FRESHNESS_INTERVALS = 2.0
FUTURE_TIMESTAMP_TOLERANCE_SECONDS = 60


class AutoPaperEngine:
    """Run one safe, signal-driven paper-trading cycle."""

    def __init__(
        self,
        symbol="BTCUSD",
        resolution=DEFAULT_RESOLUTION,
        quantity=1.0,
        ledger_path="data/paper_trades.json",
        starting_balance=5000.0,
        client=None,
        clock=None,
    ):
        self.symbol = str(symbol).upper().strip()
        self.resolution = str(resolution).strip()
        self.quantity = float(quantity)

        if self.quantity <= 0:
            raise ValueError("Paper quantity must be positive.")
        if self.resolution not in RESOLUTION_SECONDS:
            raise ValueError("Unsupported candle resolution.")

        self.client = client or DeltaPublicClient()
        self.trader = PaperTrader(
            ledger_path=ledger_path,
            starting_balance=starting_balance,
        )
        self.last_processed_candle = None
        self._clock = clock or time.time

    @staticmethod
    def _timestamp_seconds(value):
        """Parse Delta Unix timestamps (seconds or milliseconds) or ISO time."""
        if value is None or isinstance(value, bool):
            raise ValueError("Missing candle timestamp.")

        if isinstance(value, (int, float)):
            number = float(value)
            if number > 1e12:
                number /= 1000.0
            if number <= 0:
                raise ValueError("Invalid candle timestamp.")
            return number

        text = str(value).strip()
        if not text:
            raise ValueError("Missing candle timestamp.")

        # Delta candle timestamps are normally Unix seconds.
        try:
            number = float(text)
            if number > 1e12:
                number /= 1000.0
            if number <= 0:
                raise ValueError("Invalid candle timestamp.")
            return number
        except ValueError:
            pass

        # Support ISO-8601 timestamps if a provider/mock supplies them.
        try:
            normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Unparseable candle timestamp.") from exc

    def _load_candles(self):
        """Fetch candles and reject malformed, stale, or future-dated data."""
        now = float(self._clock())
        interval = RESOLUTION_SECONDS[self.resolution]
        end = int(now)
        start = end - (interval * 120)

        payload = self.client.get_candles(
            symbol=self.symbol,
            resolution=self.resolution,
            start=start,
            end=end,
        )

        if not isinstance(payload, dict):
            raise DeltaAPIError("Invalid candle response.")

        rows = payload.get("result", [])
        if not isinstance(rows, list):
            raise DeltaAPIError("Invalid candle response.")

        candles_with_time = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            try:
                raw_timestamp = row.get("time", row.get("timestamp"))
                timestamp_seconds = self._timestamp_seconds(raw_timestamp)
                candle = Candle(
                    timestamp=str(raw_timestamp),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0.0)),
                )

                values = (
                    candle.open, candle.high, candle.low,
                    candle.close, candle.volume,
                )
                if any(not (float("-inf") < value < float("inf")) for value in values):
                    continue
                if candle.volume < 0:
                    continue
                if (
                    candle.low <= 0
                    or candle.high < candle.low
                    or candle.open <= 0
                    or candle.close <= 0
                    or candle.high < candle.open
                    or candle.high < candle.close
                    or candle.low > candle.open
                    or candle.low > candle.close
                ):
                    continue

                candles_with_time.append((timestamp_seconds, candle))
            except (KeyError, TypeError, ValueError, OverflowError):
                continue

        candles_with_time.sort(key=lambda item: item[0])

        # Remove duplicate timestamps; retain the last valid row for each time.
        deduplicated = {}
        for timestamp_seconds, candle in candles_with_time:
            deduplicated[timestamp_seconds] = candle
        ordered = sorted(deduplicated.items(), key=lambda item: item[0])

        if len(ordered) < 10:
            raise DeltaAPIError("Not enough valid candles for analysis.")

        latest_time, latest = ordered[-1]
        age = now - latest_time

        if age < -FUTURE_TIMESTAMP_TOLERANCE_SECONDS:
            raise DeltaAPIError("Future-dated candle data rejected.")
        if age > interval * FRESHNESS_INTERVALS:
            raise DeltaAPIError("Stale candle data rejected.")

        # Exclude candles timestamped too far in the future from strategy input.
        safe_rows = [
            (timestamp, candle)
            for timestamp, candle in ordered
            if timestamp <= now + FUTURE_TIMESTAMP_TOLERANCE_SECONDS
        ]
        if len(safe_rows) < 10:
            raise DeltaAPIError("Not enough time-valid candles for analysis.")

        return [candle for _, candle in safe_rows]

    def run_once(self):
        """Process the newest fresh candle once; never place live orders."""
        candles = self._load_candles()
        latest = candles[-1]

        if latest.timestamp == self.last_processed_candle:
            return {
                "status": "WAITING",
                "reason": "Already processed this candle.",
                "symbol": self.symbol,
                "price": latest.close,
                "mode": "PAPER_ONLY",
                "live_orders_enabled": False,
            }

        # Only mark the candle processed after its data passes validation.
        self.last_processed_candle = latest.timestamp

        if self.trader.open_trade:
            closed = self.trader.process_candle(
                self.symbol,
                latest.high,
                latest.low,
            )
            return {
                "status": "POSITION_CLOSED" if closed else "POSITION_OPEN",
                "trade": closed or self.trader.open_trade,
                "summary": self.trader.summary(),
                "symbol": self.symbol,
                "price": latest.close,
                "mode": "PAPER_ONLY",
                "live_orders_enabled": False,
            }

        structure = analyze_market_structure(candles)
        smc = analyze_smc(candles, structure)
        ict = analyze_ict(candles, structure, smc)
        signal = generate_signal(candles, structure, smc, ict)

        result = {
            "status": "NO TRADE",
            "symbol": self.symbol,
            "price": latest.close,
            "signal": signal.signal,
            "reason": signal.reason,
            "mode": "PAPER_ONLY",
            "live_orders_enabled": False,
        }

        if signal.signal not in ("BUY", "SELL"):
            return result

        try:
            trade = self.trader.open_position(
                symbol=self.symbol,
                side=signal.signal,
                entry=latest.close,
                quantity=self.quantity,
            )
        except ValueError as exc:
            result["status"] = "TRADE_NOT_OPENED"
            result["reason"] = str(exc)
            return result

        result["status"] = "PAPER_TRADE_OPENED"
        result["trade"] = trade
        result["summary"] = self.trader.summary()
        return result
