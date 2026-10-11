"""Startup regression test for the GARRY V7 market feed."""

import unittest


class TestMarketFeedImport(unittest.TestCase):
    def test_delta_market_feed_import(self):
        from data.market_feed import DeltaMarketFeed, MarketSnapshot

        self.assertTrue(callable(DeltaMarketFeed))
        self.assertTrue(callable(MarketSnapshot))

    def test_feed_can_be_constructed(self):
        from data.market_feed import DeltaMarketFeed

        feed = DeltaMarketFeed(
            symbols=("BTCUSD",),
            client=object(),
        )

        self.assertIn("BTCUSD", feed.symbols)
        self.assertFalse(feed.running)


if __name__ == "__main__":
    unittest.main()
