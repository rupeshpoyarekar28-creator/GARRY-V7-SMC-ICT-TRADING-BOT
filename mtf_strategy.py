
"""
GARRY V7 - Multi-Timeframe SMC Engine
Analysis and backtesting only.
No exchange order functions are included.
"""

from typing import Any

# Timeframe configuration
DIRECTION_TIMEFRAME = "4h"
CONFIRMATION_TIMEFRAME = "1h"
ENTRY_TIMEFRAME = "15m"

# BTC candles API has already been tested.
BTC_SYMBOL = "BTCUSD"

# Keep unset until a tradable Delta Gold futures contract
# is verified. Do not assume XAUTUSD is a futures contract.
GOLD_SYMBOL = None

LIVE_ORDERS_ENABLED = False

STRATEGY_MODES = {
    "strict": {
        "min_structure_score": 3,
        "require_liquidity_sweep": True,
        "require_entry_confirmation": True,
    },
    "balanced": {
        "min_structure_score": 2,
        "require_liquidity_sweep": False,
        "require_entry_confirmation": True,
    },
}


def _number(value: Any) -> float:
    """Convert a candle value to a finite float."""
    import math

    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Candle value must be finite")
    return result


def get_market_structure(
    candles: list[dict],
    pivot: int = 2,
) -> dict:
    """
    Estimate swing structure using confirmed pivot highs/lows.

    Candles must be chronological and fully closed.
    A pivot is confirmed only after 'pivot' candles to its right.
    This function does not place orders.
    """
    if pivot < 1:
        return {
            "bias": "NEUTRAL",
            "reason": "Pivot size must be at least 1",
        }

    if not isinstance(candles, list) or len(candles) < 2 * pivot + 10:
        return {
            "bias": "NEUTRAL",
            "reason": "Not enough completed candles",
        }

    try:
        highs = [_number(c["high"]) for c in candles]
        lows = [_number(c["low"]) for c in candles]

        for i in range(len(candles)):
            if highs[i] < lows[i]:
                raise ValueError("Candle high is below low")

        swing_highs = []
        swing_lows = []

        # Excludes the newest candles whose pivots are not yet confirmed.
        for i in range(pivot, len(candles) - pivot):
            left_highs = highs[i - pivot:i]
            right_highs = highs[i + 1:i + pivot + 1]
            left_lows = lows[i - pivot:i]
            right_lows = lows[i + 1:i + pivot + 1]

            if all(highs[i] > x for x in left_highs + right_highs):
                swing_highs.append(highs[i])

            if all(lows[i] < x for x in left_lows + right_lows):
                swing_lows.append(lows[i])

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {
                "bias": "NEUTRAL",
                "reason": "Not enough confirmed swing points",
                "swing_highs": swing_highs[-2:],
                "swing_lows": swing_lows[-2:],
            }

        previous_high, latest_high = swing_highs[-2:]
        previous_low, latest_low = swing_lows[-2:]

        if latest_high > previous_high and latest_low > previous_low:
            bias = "BULLISH"
        elif latest_high < previous_high and latest_low < previous_low:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        return {
            "bias": bias,
            "reason": "Confirmed swing-high / swing-low comparison",
            "previous_swing_high": previous_high,
            "latest_swing_high": latest_high,
            "previous_swing_low": previous_low,
            "latest_swing_low": latest_low,
        }

    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return {
            "bias": "NEUTRAL",
            "reason": f"Invalid candle data: {exc}",
        }
