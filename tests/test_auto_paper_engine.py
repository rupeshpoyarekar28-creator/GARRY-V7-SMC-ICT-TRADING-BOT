"""Corrected AutoPaperEngine safety tests; fake data only."""
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

from data.delta_public import DeltaAPIError
from strategy.auto_paper_engine import AutoPaperEngine


class FakeDeltaClient:
    def __init__(self, rows=None, error=None):
        self.rows = list(rows or [])
        self.error = error
        self.calls = []

    def get_candles(self, symbol, resolution, start=None, end=None):
        self.calls.append({"symbol": symbol, "resolution": resolution,
                           "start": start, "end": end})
        if self.error is not None:
            raise self.error
        return {"result": list(self.rows)}


def candle(timestamp, close=100.0, volume=10.0):
    # Consistent OHLC: low <= open/close <= high.
    return {"time": timestamp, "open": close, "high": close + 1.0,
            "low": close - 1.0, "close": close, "volume": volume}


class AutoPaperEngineSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.now = 1_800_000_000.0

    def make_engine(self, rows=None, error=None, resolution="5m"):
        client = FakeDeltaClient(rows=rows, error=error)
        ledger = str(Path(self.temp_dir.name) / "paper_trades.json")
        engine = AutoPaperEngine(
            symbol="BTCUSD", resolution=resolution, quantity=1.0,
            ledger_path=ledger, starting_balance=5000.0,
            client=client, clock=lambda: self.now,
        )
        return engine, client

    def fresh_rows(self, count=12, interval=300, latest_age=30):
        latest = int(self.now - latest_age)
        first = latest - interval * (count - 1)
        return [candle(first + i * interval, close=100.0 + i)
                for i in range(count)]

    def test_fresh_valid_candles_are_accepted(self):
        rows = self.fresh_rows()
        engine, client = self.make_engine(rows=rows)
        candles = engine._load_candles()
        self.assertEqual(len(candles), len(rows))
        self.assertEqual(candles[-1].close, rows[-1]["close"])
        self.assertEqual(client.calls[0]["symbol"], "BTCUSD")
        self.assertEqual(client.calls[0]["resolution"], "5m")

    def test_stale_latest_candle_is_rejected(self):
        engine, _ = self.make_engine(rows=self.fresh_rows(latest_age=601))
        with self.assertRaisesRegex(DeltaAPIError, "Stale candle data rejected"):
            engine._load_candles()

    def test_future_dated_latest_candle_is_rejected(self):
        engine, _ = self.make_engine(rows=self.fresh_rows(latest_age=-120))
        with self.assertRaisesRegex(DeltaAPIError, "Future-dated candle data rejected"):
            engine._load_candles()

    def test_malformed_ohlc_rows_are_ignored(self):
        rows = self.fresh_rows()
        rows.append({"time": int(self.now - 10), "open": 100, "high": 90,
                     "low": 95, "close": 96, "volume": 10})
        engine, _ = self.make_engine(rows=rows)
        candles = engine._load_candles()
        self.assertTrue(all(item.high >= item.low for item in candles))
        self.assertEqual(len(candles), 12)

    def test_duplicate_timestamps_are_deduplicated(self):
        rows = self.fresh_rows()
        rows.append(dict(rows[-1]))
        engine, _ = self.make_engine(rows=rows)
        self.assertEqual(len(engine._load_candles()), 12)

    def test_too_few_valid_candles_are_rejected(self):
        engine, _ = self.make_engine(rows=self.fresh_rows(count=9))
        with self.assertRaisesRegex(DeltaAPIError, "Not enough valid candles"):
            engine._load_candles()

    def test_api_errors_propagate_without_fabricated_data(self):
        engine, _ = self.make_engine(
            error=DeltaAPIError("NETWORK ERROR: test timeout"))
        with self.assertRaisesRegex(DeltaAPIError, "NETWORK ERROR"):
            engine._load_candles()

    def test_invalid_resolution_is_rejected_at_initialization(self):
        with self.assertRaisesRegex(ValueError, "Unsupported candle resolution"):
            self.make_engine(resolution="7m")

    def test_millisecond_timestamps_are_supported(self):
        rows = self.fresh_rows()
        for row in rows:
            row["time"] = int(row["time"]) * 1000
        engine, _ = self.make_engine(rows=rows)
        self.assertEqual(len(engine._load_candles()), 12)

    def test_iso_timestamps_are_supported(self):
        rows = self.fresh_rows()
        for row in rows:
            row["time"] = datetime.fromtimestamp(
                row["time"], timezone.utc
            ).isoformat().replace("+00:00", "Z")
        engine, _ = self.make_engine(rows=rows)
        self.assertEqual(len(engine._load_candles()), 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
