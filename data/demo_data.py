"""
GARRY V7 SMC ICT TRADING BOT

Deterministic demo market data.

This module provides mock OHLC data for the first build.
No internet connection, API key, broker SDK, or V8 module
is required.
"""

from data.models import Candle, MarketData, create_market_data


def get_demo_candles() -> list[Candle]:
    """Return deterministic demo 5-minute OHLC candles."""

    raw_candles = [
        ("09:15", 100.00, 101.00, 99.50, 100.50),
        ("09:20", 100.50, 101.50, 100.00, 101.20),
        ("09:25", 101.20, 102.00, 100.80, 101.80),
        ("09:30", 101.80, 102.40, 101.30, 102.10),
        ("09:35", 102.10, 102.60, 101.60, 102.40),
        ("09:40", 102.40, 102.50, 101.70, 102.00),
        ("09:45", 102.00, 102.20, 101.20, 101.50),
        ("09:50", 101.50, 101.90, 100.90, 101.20),
        ("09:55", 101.20, 102.30, 101.00, 102.10),
        ("10:00", 102.10, 103.00, 101.80, 102.80),
        ("10:05", 102.80, 103.60, 102.50, 103.40),
        ("10:10", 103.40, 104.20, 103.00, 103.90),
    ]

    return [
        Candle(
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=1000.0,
        )
        for timestamp, open_price, high, low, close in raw_candles
    ]


def get_demo_market_data() -> MarketData:
    """Return the default demo market-data snapshot."""

    candles = get_demo_candles()

    return create_market_data(
        symbol="BTCUSDT",
        timeframe="5m",
        price=candles[-1].close,
        connection_status="DEMO",
        candles=candles,
    )
