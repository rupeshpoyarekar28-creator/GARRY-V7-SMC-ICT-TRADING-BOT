"""
GARRY V7 — AUTOMATIC PAPER TRADING ENGINE

Public Delta market data only.
No authentication and no live order execution.
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


class AutoPaperEngine:
    """Run one safe, signal-driven paper-trading cycle."""

    def __init__(
        self,
        symbol="BTCUSD",
        resolution="5m",
        quantity=1.0,
        ledger_path="data/paper_trades.json",
        starting_balance=5000.0,
    ):
        self.symbol = symbol.upper().strip()
        self.resolution = resolution
        self.quantity = float(quantity)

        if self.quantity <= 0:
            raise ValueError("Paper quantity must be positive.")

        self.client = DeltaPublicClient()
        self.trader = PaperTrader(
            ledger_path=ledger_path,
            starting_balance=starting_balance,
        )

        self.last_processed_candle = None

    def _load_candles(self):
        """Fetch and validate recent public candles."""

        end = int(time.time())
        start = end - (300 * 120)

        payload = self.client.get_candles(
            symbol=self.symbol,
            resolution=self.resolution,
            start=start,
            end=end,
        )

        rows = payload.get("result", [])

        if not isinstance(rows, list):
            raise DeltaAPIError("Invalid candle response.")

        candles = []

        for row in rows:
            if not isinstance(row, dict):
                continue

            try:
                timestamp = row.get(
                    "time",
                    row.get("timestamp", ""),
                )

                candle = Candle(
                    timestamp=str(timestamp),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0.0)),
                )

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

                candles.append(candle)

            except (KeyError, TypeError, ValueError):
                continue

        candles.sort(key=lambda candle: candle.timestamp)

        if len(candles) < 10:
            raise DeltaAPIError(
                "Not enough valid candles for analysis."
            )

        return candles

    def run_once(self):
        """
        Process the latest available candle once.
        Call repeatedly from a controlled scheduler.
        """

        candles = self._load_candles()
        latest = candles[-1]

        # Avoid processing the same candle repeatedly.
        if latest.timestamp == self.last_processed_candle:
            return {
                "status": "WAITING",
                "reason": "Already processed this candle.",
                "symbol": self.symbol,
            }

        self.last_processed_candle = latest.timestamp

        # Manage an existing paper position first.
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
                "mode": "PAPER_ONLY",
            }

        structure = analyze_market_structure(candles)
        smc = analyze_smc(candles, structure)
        ict = analyze_ict(candles, structure, smc)
        signal = generate_signal(
            candles,
            structure,
            smc,
            ict,
        )

        result = {
            "status": "NO TRADE",
            "symbol": self.symbol,
            "price": latest.close,
            "signal": signal.signal,
            "reason": signal.reason,
            "mode": "PAPER_ONLY",
        }

        if signal.signal not in ("BUY", "SELL"):
            return result

        # PaperTrader enforces its own daily limit and
        # fixed 15-point SL / 20-point TP.
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
