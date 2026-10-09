
"""
GARRY V7 — PAPER TRADING ONLY
No exchange orders are placed by this module.
"""

import json
import os
from datetime import datetime, timezone

DEFAULT_TP_POINTS = 20.0
DEFAULT_SL_POINTS = 15.0
MAX_TRADES_PER_DAY = 4


class PaperTradingError(ValueError):
    pass


class PaperTrader:
    def __init__(
        self,
        ledger_path="data/paper_trades.json",
        starting_balance=5000.0,
    ):
        if starting_balance <= 0:
            raise PaperTradingError("Invalid starting balance")

        self.ledger_path = ledger_path
        self.starting_balance = float(starting_balance)
        self.trades = []
        self._load()

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    def _load(self):
        if not os.path.exists(self.ledger_path):
            return

        try:
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("mode") != "PAPER_ONLY":
                raise PaperTradingError("Invalid ledger mode")
            self.trades = data.get("trades", [])
        except (OSError, json.JSONDecodeError) as exc:
            raise PaperTradingError(f"Cannot load ledger: {exc}") from exc

    def _save(self):
        folder = os.path.dirname(self.ledger_path) or "."
        os.makedirs(folder, exist_ok=True)

        temp_path = self.ledger_path + ".tmp"
        data = {
            "mode": "PAPER_ONLY",
            "live_orders_enabled": False,
            "starting_balance": self.starting_balance,
            "updated_at": self.now(),
            "trades": self.trades,
        }

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        os.replace(temp_path, self.ledger_path)

    @property
    def open_trade(self):
        return next(
            (t for t in reversed(self.trades)
             if t["status"] == "OPEN"),
            None,
        )

    def open_position(self, symbol, side, entry, quantity):
        symbol = symbol.strip().upper()
        side = side.strip().upper()
        entry = float(entry)
        quantity = float(quantity)

        if not symbol or side not in ("BUY", "SELL"):
            raise PaperTradingError("Invalid symbol or side")

        if entry <= 0 or quantity <= 0:
            raise PaperTradingError("Entry and quantity must be positive")

        if self.open_trade:
            raise PaperTradingError("A position is already open")

        today = datetime.now(timezone.utc).date().isoformat()
        today_count = sum(
            t["opened_at"][:10] == today for t in self.trades
        )
        if today_count >= MAX_TRADES_PER_DAY:
            raise PaperTradingError("Daily limit: four trades reached")

        if side == "BUY":
            sl = entry - DEFAULT_SL_POINTS
            tp = entry + DEFAULT_TP_POINTS
        else:
            sl = entry + DEFAULT_SL_POINTS
            tp = entry - DEFAULT_TP_POINTS

        if sl <= 0 or tp <= 0:
            raise PaperTradingError("Invalid calculated SL/TP")

        trade = {
            "id": max(
                (t["id"] for t in self.trades), default=0
            ) + 1,
            "symbol": symbol,
            "side": side,
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp,
            "quantity": quantity,
            "opened_at": self.now(),
            "status": "OPEN",
            "exit_price": None,
            "pnl": 0.0,
            "close_reason": None,
        }

        self.trades.append(trade)
        self._save()
        return trade

    def process_candle(self, symbol, high, low):
        trade = self.open_trade
        if not trade or trade["symbol"] != symbol.upper():
            return None

        high, low = float(high), float(low)
        if low <= 0 or high < low:
            raise PaperTradingError("Invalid candle")

        if trade["side"] == "BUY":
            sl_hit = low <= trade["stop_loss"]
            tp_hit = high >= trade["take_profit"]
        else:
            sl_hit = high >= trade["stop_loss"]
            tp_hit = low <= trade["take_profit"]

        # If both levels are touched, assume SL first.
        if sl_hit:
            return self.close_position(
                trade["id"], trade["stop_loss"], "STOP_LOSS"
            )
        if tp_hit:
            return self.close_position(
                trade["id"], trade["take_profit"], "TAKE_PROFIT"
            )

        return None

    def close_position(self, trade_id, exit_price, reason):
        trade = next(
            (t for t in self.trades if t["id"] == trade_id),
            None,
        )
        if not trade or trade["status"] != "OPEN":
            raise PaperTradingError("Open paper trade not found")

        exit_price = float(exit_price)
        if exit_price <= 0:
            raise PaperTradingError("Invalid exit price")

        if trade["side"] == "BUY":
            pnl = (exit_price - trade["entry"]) * trade["quantity"]
        else:
            pnl = (trade["entry"] - exit_price) * trade["quantity"]

        trade["status"] = "CLOSED"
        trade["exit_price"] = exit_price
        trade["closed_at"] = self.now()
        trade["pnl"] = round(pnl, 8)
        trade["close_reason"] = reason

        self._save()
        return trade

    def summary(self):
        closed = [t for t in self.trades if t["status"] == "CLOSED"]
        pnl = sum(t["pnl"] for t in closed)

        return {
            "mode": "PAPER_ONLY",
            "live_orders_enabled": False,
            "starting_balance": self.starting_balance,
            "realized_pnl": round(pnl, 8),
            "equity": round(self.starting_balance + pnl, 8),
            "total_trades": len(self.trades),
            "closed_trades": len(closed),
            "wins": sum(t["pnl"] > 0 for t in closed),
            "losses": sum(t["pnl"] < 0 for t in closed),
        }
