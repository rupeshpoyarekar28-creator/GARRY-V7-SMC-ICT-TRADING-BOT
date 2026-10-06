"""
GARRY V7 SMC ICT TRADING BOT

Clean market data models used by the strategy engine.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    """Represents one OHLC market candle."""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class MarketData:
    """Represents the current demo market state."""

    symbol: str
    timeframe: str
    price: float
    connection_status: str
    candles: tuple[Candle, ...]


def create_market_data(
    symbol: str,
    timeframe: str,
    price: float,
    connection_status: str,
    candles: list[Candle],
) -> MarketData:
    """Create an immutable MarketData object."""

    return MarketData(
        symbol=symbol,
        timeframe=timeframe,
        price=price,
        connection_status=connection_status,
        candles=tuple(candles),
    )
