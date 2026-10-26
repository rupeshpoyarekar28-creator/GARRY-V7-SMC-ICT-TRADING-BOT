
from __future__ import annotations

from math import isfinite
from typing import Any


# ============================================================
# GARRY V7 - ICT / SMC STRATEGY
# Historical backtesting signal engine only.
# No API keys. No order execution. No live trading.
# ============================================================

HTF_TIMEFRAME = "1h"
POI_TIMEFRAME = "15m"
ENTRY_TIMEFRAME = "5m"

MIN_HTF_CANDLES = 30
MIN_POI_CANDLES = 25
MIN_ENTRY_CANDLES = 30

SWING_LOOKBACK = 10
LIQUIDITY_LOOKBACK = 10
FVG_LOOKBACK = 10

LIVE_ORDERS_ENABLED = False

STRATEGY_MODES = {
    "strict": {
        "require_sweep": True,
        "require_fvg": True,
        "require_displacement": True,
    },
    "balanced": {
        "require_sweep": True,
        "require_fvg": False,
        "require_displacement": False,
    },
}


def _number(value: Any) -> float:
    """Convert a value to a finite float."""
    result = float(value)
    if not isfinite(result):
        raise ValueError("Non-finite candle value")
    return result


def _validate_candles(candles: list[dict]) -> list[dict]:
    """Validate and copy OHLC candles."""
    if not isinstance(candles, list):
        raise ValueError("Candles must be a list")

    cleaned = []

    for candle in candles:
        if not isinstance(candle, dict):
            raise ValueError("Each candle must be a dictionary")

        item = {
            "open": _number(candle["open"]),
            "high": _number(candle["high"]),
            "low": _number(candle["low"]),
            "close": _number(candle["close"]),
        }

        if item["high"] < item["low"]:
            raise ValueError("Candle high is below candle low")

        if item["high"] < max(item["open"], item["close"]):
            raise ValueError("Candle high is below open/close")

        if item["low"] > min(item["open"], item["close"]):
            raise ValueError("Candle low is above open/close")

        cleaned.append(item)

    return cleaned


def _trend(candles: list[dict]) -> str:
    """
    Basic HTF directional bias using recent swing structure.
    Returns BULLISH, BEARISH, or NEUTRAL.
    """
    data = candles[:-1]

    if len(data) < MIN_HTF_CANDLES:
        return "NEUTRAL"

    recent = data[-20:]
    earlier = data[-30:-10]

    recent_high = max(c["high"] for c in recent)
    earlier_high = max(c["high"] for c in earlier)
    recent_low = min(c["low"] for c in recent)
    earlier_low = min(c["low"] for c in earlier)

    if recent_high > earlier_high and recent_low > earlier_low:
        return "BULLISH"

    if recent_high < earlier_high and recent_low < earlier_low:
        return "BEARISH"

    return "NEUTRAL"


def _liquidity_sweep(candles: list[dict]) -> dict:
    """Check whether the latest completed candle swept a prior level."""
    data = candles[:-1]
    current = candles[-1]

    if len(data) < LIQUIDITY_LOOKBACK:
        return {"type": "NONE", "level": None}

    reference = data[-LIQUIDITY_LOOKBACK:]
    previous_high = max(c["high"] for c in reference)
    previous_low = min(c["low"] for c in reference)

    # Swept highs and closed back below: possible bearish reversal.
    if (
        current["high"] > previous_high
        and current["close"] < previous_high
    ):
        return {
            "type": "BUY_SIDE_SWEEP",
            "level": previous_high,
        }

    # Swept lows and closed back above: possible bullish reversal.
    if (
        current["low"] < previous_low
        and current["close"] > previous_low
    ):
        return {
            "type": "SELL_SIDE_SWEEP",
            "level": previous_low,
        }

    return {"type": "NONE", "level": None}


def _fvg(candles: list[dict]) -> dict:
    """
    Find a recent three-candle Fair Value Gap.
    Bullish FVG: candle 3 low > candle 1 high.
    Bearish FVG: candle 3 high < candle 1 low.
    """
    data = candles[:-1]

    if len(data) < 3:
        return {"type": "NONE", "low": None, "high": None}

    start = max(2, len(data) - FVG_LOOKBACK)

    for i in range(len(data) - 1, start - 1, -1):
        first = data[i - 2]
        third = data[i]

        if third["low"] > first["high"]:
            return {
                "type": "BULLISH",
                "low": first["high"],
                "high": third["low"],
            }

        if third["high"] < first["low"]:
            return {
                "type": "BEARISH",
                "low": third["high"],
                "high": first["low"],
            }

    return {"type": "NONE", "low": None, "high": None}


def _structure_shift(candles: list[dict]) -> dict:
    """
    Basic MSS/CHoCH proxy:
    close breaks the recent completed-candle high or low.
    This is not a full pivot-confirmed ICT structure algorithm.
    """
    data = candles[:-1]
    current = candles[-1]

    if len(data) < SWING_LOOKBACK:
        return {"type": "NONE", "level": None}

    reference = data[-SWING_LOOKBACK:]
    recent_high = max(c["high"] for c in reference)
    recent_low = min(c["low"] for c in reference)

    if current["close"] > recent_high:
        return {"type": "BULLISH", "level": recent_high}

    if current["close"] < recent_low:
        return {"type": "BEARISH", "level": recent_low}

    return {"type": "NONE", "level": None}


def _displacement(candles: list[dict]) -> bool:
    """Simple candle-body expansion check."""
    data = candles[:-1]

    if len(data) < 11:
        return False

    current = data[-1]
    body = abs(current["close"] - current["open"])

    previous_bodies = [
        abs(c["close"] - c["open"])
        for c in data[-11:-1]
    ]

    average_body = sum(previous_bodies) / len(previous_bodies)

    return average_body > 0 and body >= 1.5 * average_body


def detect_ict_signal(
    htf_candles: list[dict],
    poi_candles: list[dict],
    entry_candles: list[dict],
    mode: str = "strict",
    symbol: str = "BTCUSD",
) -> dict:
    """
    Analyse completed candles from three timeframes.

    Inputs must be chronological (oldest first).
    The final candle in each input is treated as the latest
    candle supplied by the caller. Pass completed candles only.

    Returns WAIT, BUY_WATCH, or SELL_WATCH.
    Does not place orders or calculate a guaranteed trade outcome.
    """
    if mode not in STRATEGY_MODES:
        return {
            "signal": "WAIT",
            "reason": "Mode must be strict or balanced",
        }

    try:
        htf = _validate_candles(htf_candles)
        poi = _validate_candles(poi_candles)
        entry = _validate_candles(entry_candles)

        if len(htf) < MIN_HTF_CANDLES:
            return {"signal": "WAIT", "reason": "Need more 1H candles"}

        if len(poi) < MIN_POI_CANDLES:
            return {"signal": "WAIT", "reason": "Need more 15M candles"}

        if len(entry) < MIN_ENTRY_CANDLES:
            return {"signal": "WAIT", "reason": "Need more 5M candles"}

        # Exclude the latest candle from directional calculations
        # where possible. The caller must provide closed candles.
        bias = _trend(htf)
        sweep = _liquidity_sweep(poi)
        shift = _structure_shift(entry)
        gap = _fvg(entry)
        displacement = _displacement(entry)

        settings = STRATEGY_MODES[mode]

        buy_conditions = (
            bias == "BULLISH"
            and sweep["type"] == "SELL_SIDE_SWEEP"
            and shift["type"] == "BULLISH"
        )

        sell_conditions = (
            bias == "BEARISH"
            and sweep["type"] == "BUY_SIDE_SWEEP"
            and shift["type"] == "BEARISH"
        )

        if settings["require_fvg"]:
            buy_conditions = buy_conditions and gap["type"] == "BULLISH"
            sell_conditions = sell_conditions and gap["type"] == "BEARISH"

        if settings["require_displacement"]:
            buy_conditions = buy_conditions and displacement
            sell_conditions = sell_conditions and displacement

        if buy_conditions:
            return {
                "signal": "BUY_WATCH",
                "symbol": symbol,
                "mode": mode,
                "bias_1h": bias,
                "sweep_15m": sweep,
                "structure_5m": shift,
                "fvg_5m": gap,
                "displacement": displacement,
                "reason": "Bullish HTF bias + sell-side sweep + bullish structure shift",
                "live_orders_enabled": LIVE_ORDERS_ENABLED,
            }

        if sell_conditions:
            return {
                "signal": "SELL_WATCH",
                "symbol": symbol,
                "mode": mode,
                "bias_1h": bias,
                "sweep_15m": sweep,
                "structure_5m": shift,
                "fvg_5m": gap,
                "displacement": displacement,
                "reason": "Bearish HTF bias + buy-side sweep + bearish structure shift",
                "live_orders_enabled": LIVE_ORDERS_ENABLED,
            }

        return {
            "signal": "WAIT",
            "symbol": symbol,
            "mode": mode,
            "bias_1h": bias,
            "sweep_15m": sweep,
            "structure_5m": shift,
            "fvg_5m": gap,
            "displacement": displacement,
            "reason": "All required setup conditions are not aligned",
            "live_orders_enabled": LIVE_ORDERS_ENABLED,
        }

    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return {
            "signal": "WAIT",
            "reason": f"Invalid candle data: {exc}",
            "live_orders_enabled": LIVE_ORDERS_ENABLED,
        }
