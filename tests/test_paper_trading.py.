"""Unit tests for GARRY V7 paper trading."""

import json
import tempfile
import unittest
from pathlib import Path

from strategy.paper_trading import (
    PaperTrader,
    PaperTradingError,
    DEFAULT_TP_POINTS,
    DEFAULT_SL_POINTS,
    MAX_TRADES_PER_DAY,
)


class TestPaperTrading(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ledger = str(Path(self.temp_dir.name) / "paper_trades.json")
        self.trader = PaperTrader(
            ledger_path=self.ledger,
            starting_balance=5000.0,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_final_limits_and_paper_only_mode(self):
        self.assertEqual(MAX_TRADES_PER_DAY, 4)
        self.assertEqual(DEFAULT_TP_POINTS, 20.0)
        self.assertEqual(DEFAULT_SL_POINTS, 15.0)
        self.assertFalse(self.trader.summary()["live_orders_enabled"])

    def test_buy_take_profit(self):
        trade = self.trader.open_position("BTCUSD", "BUY", 100.0, 1.0)

        self.assertEqual(trade["stop_loss"], 85.0)
        self.assertEqual(trade["take_profit"], 120.0)

        closed = self.trader.process_candle("BTCUSD", high=120.0, low=101.0)

        self.assertEqual(closed["status"], "CLOSED")
        self.assertEqual(closed["close_reason"], "TAKE_PROFIT")
        self.assertEqual(closed["pnl"], 20.0)

    def test_sell_take_profit(self):
        trade = self.trader.open_position("BTCUSD", "SELL", 100.0, 1.0)

        self.assertEqual(trade["stop_loss"], 115.0)
        self.assertEqual(trade["take_profit"], 80.0)

        closed = self.trader.process_candle("BTCUSD", high=99.0, low=80.0)

        self.assertEqual(closed["close_reason"], "TAKE_PROFIT")
        self.assertEqual(closed["pnl"], 20.0)

    def test_buy_stop_loss(self):
        self.trader.open_position("BTCUSD", "BUY", 100.0, 1.0)

        closed = self.trader.process_candle("BTCUSD", high=105.0, low=85.0)

        self.assertEqual(closed["close_reason"], "STOP_LOSS")
        self.assertEqual(closed["pnl"], -15.0)

    def test_stop_loss_wins_if_both_levels_touched(self):
        self.trader.open_position("BTCUSD", "BUY", 100.0, 1.0)

        closed = self.trader.process_candle("BTCUSD", high=120.0, low=85.0)

        self.assertEqual(closed["close_reason"], "STOP_LOSS")
        self.assertEqual(closed["pnl"], -15.0)

    def test_only_one_open_position(self):
        self.trader.open_position("BTCUSD", "BUY", 100.0, 1.0)

        with self.assertRaises(PaperTradingError):
            self.trader.open_position("ETHUSD", "BUY", 100.0, 1.0)

    def test_invalid_side_rejected(self):
        with self.assertRaises(PaperTradingError):
            self.trader.open_position("BTCUSD", "HOLD", 100.0, 1.0)

    def test_invalid_entry_rejected(self):
        with self.assertRaises(PaperTradingError):
            self.trader.open_position("BTCUSD", "BUY", 0.0, 1.0)

    def test_ledger_persists_after_reload(self):
        self.trader.open_position("BTCUSD", "BUY", 100.0, 1.0)

        reloaded = PaperTrader(
            ledger_path=self.ledger,
            starting_balance=5000.0,
        )

        self.assertEqual(len(reloaded.trades), 1)
        self.assertEqual(reloaded.trades[0]["symbol"], "BTCUSD")
        self.assertEqual(reloaded.trades[0]["status"], "OPEN")

        with open(self.ledger, "r", encoding="utf-8") as file:
            data = json.load(file)

        self.assertEqual(data["mode"], "PAPER_ONLY")
        self.assertFalse(data["live_orders_enabled"])

    def test_summary_after_closed_trade(self):
        self.trader.open_position("BTCUSD", "BUY", 100.0, 2.0)
        self.trader.process_candle("BTCUSD", high=120.0, low=101.0)

        summary = self.trader.summary()

        self.assertEqual(summary["closed_trades"], 1)
        self.assertEqual(summary["wins"], 1)
        self.assertEqual(summary["losses"], 0)
        self.assertEqual(summary["realized_pnl"], 40.0)
        self.assertEqual(summary["equity"], 5040.0)
        self.assertFalse(summary["live_orders_enabled"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
