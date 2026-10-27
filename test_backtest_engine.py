import unittest
from backtest_engine import (
    DEFAULT_SETTINGS, _fee_inr, _gross_pnl_inr, _estimated_stop_loss_inr,
    run_backtest
)

class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.cfg = DEFAULT_SETTINGS.copy()

    def test_one_lot_gross_pnl_20_dollar_move(self):
        # $20 * 0.001 BTC * ₹85/USD = ₹1.70
        self.assertAlmostEqual(_gross_pnl_inr(80000, 80020, "BUY", 1, self.cfg), 1.70, places=8)
        self.assertAlmostEqual(_gross_pnl_inr(80000, 79980, "SELL", 1, self.cfg), 1.70, places=8)

    def test_one_lot_fee_with_gst(self):
        # Notional = $80 * 0.05% = $0.04; convert to INR, then GST.
        fee = _fee_inr(80000, 1, self.cfg)
        self.assertAlmostEqual(fee, 3.40, places=8)  # fee before GST, one side
        round_trip_including_gst = 2 * fee * (1 + self.cfg["fee_gst_rate"])
        self.assertAlmostEqual(round_trip_including_gst, 8.024, places=6)

    def test_existing_tp_is_negative_after_costs(self):
        gross = _gross_pnl_inr(80000, 80020, "BUY", 1, self.cfg)
        fees = _fee_inr(80000, 1, self.cfg) + _fee_inr(80020, 1, self.cfg)
        net = gross - fees * (1 + self.cfg["fee_gst_rate"])
        self.assertLess(net, 0)

    def test_risk_estimate_includes_costs(self):
        risk = _estimated_stop_loss_inr(80000, "BUY", 1, self.cfg)
        self.assertGreater(risk, 8.0)
        self.assertLess(risk, 10.0)

    def test_rejects_other_symbol(self):
        with self.assertRaises(ValueError):
            run_backtest([], [], [], symbol="XAUTUSD")

if __name__ == "__main__":
    unittest.main(verbosity=2)
