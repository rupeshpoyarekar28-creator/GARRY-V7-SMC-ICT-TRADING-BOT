
from dataclasses import dataclass
from typing import Optional


@dataclass
class Signal:
    side: str
    reason: str
    close: float
    stop_loss: Optional[float] = None


def detect_signal(candles: list[dict]) -> dict:
    """
    Educational market-structure prototype.

    Each candle must contain:
    open, high, low, close

    Candles must be chronological and completed.
    This prototype does not place orders.
    """
    if len(candles) < 20:
        return {
            "signal": "WAIT",
            "reason": "Need at least 20 completed candles"
        }

    for candle in candles:
        for key in ("open", "high", "low", "close"):
            if key not in candle:
                return {
                    "signal": "WAIT",
                    "reason": f"Missing candle field: {key}"
                }

    # Use only candles before the latest completed candle
    # to calculate reference high/low levels.
    previous = candles[-21:-1]
    current = candles[-1]

    swing_high = max(float(c["high"]) for c in previous)
    swing_low = min(float(c["low"]) for c in previous)

    high = float(current["high"])
    low = float(current["low"])
    close = float(current["close"])

    # Liquidity sweep followed by a close back inside range.
    if high > swing_high and close < swing_high:
        return {
            "signal": "SELL_WATCH",
            "reason": "Potential buy-side liquidity sweep",
            "reference_level": swing_high,
            "close": close
        }

    if low < swing_low and close > swing_low:
        return {
            "signal": "BUY_WATCH",
            "reason": "Potential sell-side liquidity sweep",
            "reference_level": swing_low,
            "close": close
        }

    # Breakout checks use closing price, not wick alone.
    if close > swing_high:
        return {
            "signal": "BULLISH_BREAKOUT",
            "reason": "Close above prior 20-candle high",
            "reference_level": swing_high,
            "close": close
        }

    if close < swing_low:
        return {
            "signal": "BEARISH_BREAKOUT",
            "reason": "Close below prior 20-candle low",
            "reference_level": swing_low,
            "close": close
        }

    return {
        "signal": "WAIT",
        "reason": "No qualifying setup",
        "reference_high": swing_high,
        "reference_low": swing_low,
        "close": close
    }
