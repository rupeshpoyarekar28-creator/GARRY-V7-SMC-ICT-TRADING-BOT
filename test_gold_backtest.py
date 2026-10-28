import unittest

from gold_backtest_engine import (
    DEFAULT_SETTINGS,
    LIVE_ORDERS_ENABLED,
    validate_candles,
)


class GoldBacktestTests(unittest.TestCase):

    def test_live_trading_is_disabled(self):
        self.assertFalse(LIVE_ORDERS_ENABLED)

    def test_default_lot_size(self):
        self.assertEqual(DEFAULT_SETTINGS["lot_size"], 0.03)

    def test_take_profit(self):
        self.assertEqual(
            DEFAULT_SETTINGS["take_profit_price"], 20.0
        )

    def test_stop_loss(self):
        self.assertEqual(
            DEFAULT_SETTINGS["stop_loss_price"], 15.0
        )

    def test_daily_trade_limit(self):
        self.assertEqual(
            DEFAULT_SETTINGS["max_trades_per_day"], 4
        )

    def test_valid_candle(self):
        candles = [{
            "time": 1790000000,
            "open": 4000.0,
            "high": 4010.0,
            "low": 3990.0,
            "close": 4005.0,
        }]

        result = validate_candles(candles, "test", 300)
        self.assertEqual(len(result), 1)

    def test_invalid_high_is_rejected(self):
        candles = [{
            "time": 1790000000,
            "open": 4000.0,
            "high": 3990.0,
            "low": 3980.0,
            "close": 4005.0,
        }]

        with self.assertRaises(ValueError):
            validate_candles(candles, "test", 300)


if __name__ == "__main__":
    unittest.main()
