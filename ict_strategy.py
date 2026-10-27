
from __future__ import annotations

from math import isfinite
from typing import Any


# ============================================================
# GARRY V7 - ICT / SMC SIGNAL ENGINE
# Historical backtesting and diagnostics only.
# No API keys. No exchange orders. No live trading.
# ============================================================

HTF_TIMEFRAME = "1h"
POI_TIMEFRAME = "15m"
ENTRY_TIMEFRAME = "5m"

MIN_HTF_CANDLES = 30
MIN_POI_CANDLES = 25
MIN_ENTRY_CANDLES = 30

TREND_WINDOW = 20
LIQUIDITY_LOOKBACK = 10
STRUCTURE_LOOKBACK = 10
FVG_LOOKBACK = 10
DISPLACEMENT_LOOKBACK = 10

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
    result = float(value)
    if not isfinite(result):
        raise ValueError("Non-finite candle value")
    return result


def _validate_candles(candles: list[dict]) -> list[dict]:
    if not isinstance(candles, list):
        raise ValueError("Candles must be a list")

    cleaned = []

    for index, candle in enumerate(candles):
        if not isinstance(candle, dict):
            raise ValueError(f"Candle {index} must be a dictionary")

        item = {
            "open": _number(candle["open"]),
            "high": _number(candle["high"]),
            "low": _number(candle["low"]),
            "close": _number(candle["close"]),
        }

        if item["high"] < max(item["open"], item["close"], item["low"]):
            raise ValueError(f"Invalid high in candle {index}")

        if item["low"] > min(item["open"], item["close"], item["high"]):
            raise ValueError(f"Invalid low in candle {index}")

        cleaned.append(item)

    return cleaned


def _trend(candles: list[dict]) -> dict:
    """
    Use only the candles passed by the caller.
    The caller must supply completed candles only.

    Compares two non-overlapping 20-candle windows.
    This is a simple directional proxy, not full ICT structure.
    """
    if len(candles) < TREND_WINDOW * 2:
        return {
            "type": "NEUTRAL",
            "reason": "Need 40 completed 1H candles for trend comparison",
        }

    earlier = candles[-TREND_WINDOW * 2:-TREND_WINDOW]
    recent = candles[-TREND_WINDOW:]

    earlier_high = max(c["high"] for c in earlier)
    earlier_low = min(c["low"] for c in earlier)
    recent_high = max(c["high"] for c in recent)
    recent_low = min(c["low"] for c in recent)

    if recent_high > earlier_high and recent_low > earlier_low:
        return {
            "type": "BULLISH",
            "reason": "Recent 1H range high and low are both higher",
        }

    if recent_high < earlier_high and recent_low < earlier_low:
        return {
            "type": "BEARISH",
            "reason": "Recent 1H range high and low are both lower",
        }

    return {
        "type": "NEUTRAL",
        "reason": "1H range structure is mixed",
    }


def _liquidity_sweep(candles: list[dict]) -> dict:
    """
    Latest candle is the most recent completed 15M candle.
    Compare its wick against the preceding candles only.
    """
    if len(candles) < LIQUIDITY_LOOKBACK + 1:
        return {
            "type": "NONE",
            "level": None,
            "reason": "Insufficient 15M candles for sweep check",
        }

    current = candles[-1]
    reference = candles[-LIQUIDITY_LOOKBACK - 1:-1]

    previous_high = max(c["high"] for c in reference)
    previous_low = min(c["low"] for c in reference)

    if (
        current["high"] > previous_high
        and current["close"] < previous_high
    ):
        return {
            "type": "BUY_SIDE_SWEEP",
            "level": previous_high,
            "reason": "Price swept prior highs and closed back below",
        }

    if (
        current["low"] < previous_low
        and current["close"] > previous_low
    ):
        return {
            "type": "SELL_SIDE_SWEEP",
            "level": previous_low,
            "reason": "Price swept prior lows and closed back above",
        }

    return {
        "type": "NONE",
        "level": None,
        "reason": "Latest completed 15M candle did not sweep a prior level",
    }


def _structure_shift(candles: list[dict]) -> dict:
    """
    Basic MSS/CHoCH proxy:
    completed candle closes beyond the previous swing window.
    Not a full pivot-confirmed ICT implementation.
    """
    if len(candles) < STRUCTURE_LOOKBACK + 1:
        return {
            "type": "NONE",
            "level": None,
            "reason": "Insufficient 5M candles for structure check",
        }

    current = candles[-1]
    reference = candles[-STRUCTURE_LOOKBACK - 1:-1]

    previous_high = max(c["high"] for c in reference)
    previous_low = min(c["low"] for c in reference)

    if current["close"] > previous_high:
        return {
            "type": "BULLISH",
            "level": previous_high,
            "reason": "5M close broke above the previous range high",
        }

    if current["close"] < previous_low:
        return {
            "type": "BEARISH",
            "level": previous_low,
            "reason": "5M close broke below the previous range low",
        }

    return {
        "type": "NONE",
        "level": None,
        "reason": "No 5M close beyond the previous range",
    }


def _fvg(candles: list[dict]) -> dict:
    """
    Find the most recent three-candle FVG in the supplied
    completed 5M candles.

    Bullish: third candle low > first candle high.
    Bearish: third candle high < first candle low.
    """
    if len(candles) < 3:
        return {
            "type": "NONE",
            "low": None,
            "high": None,
            "reason": "Insufficient candles for FVG",
        }

    start = max(2, len(candles) - FVG_LOOKBACK)

    for i in range(len(candles) - 1, start - 1, -1):
        first = candles[i - 2]
        third = candles[i]

        if third["low"] > first["high"]:
            return {
                "type": "BULLISH",
                "low": first["high"],
                "high": third["low"],
                "reason": "Bullish three-candle gap detected",
            }

        if third["high"] < first["low"]:
            return {
                "type": "BEARISH",
                "low": third["high"],
                "high": first["low"],
                "reason": "Bearish three-candle gap detected",
            }

    return {
        "type": "NONE",
        "low": None,
        "high": None,
        "reason": "No recent FVG found",
    }


def _displacement(candles: list[dict]) -> dict:
    """
    Current completed candle body must be at least 1.5 times
    the average body of the preceding 10 completed candles.
    """
    required = DISPLACEMENT_LOOKBACK + 1

    if len(candles) < required:
        return {
            "detected": False,
            "body": None,
            "average_body": None,
            "reason": "Insufficient candles for displacement check",
        }

    current = candles[-1]
    body = abs(current["close"] - current["open"])

    previous = candles[-required:-1]
    bodies = [
        abs(c["close"] - c["open"])
        for c in previous
    ]

    average_body = sum(bodies) / len(bodies)

    detected = average_body > 0 and body >= 1.5 * average_body

    return {
        "detected": detected,
        "body": body,
        "average_body": average_body,
        "reason": (
            "Candle body expansion detected"
            if detected
            else "Candle body did not reach 1.5x average"
        ),
    }


def detect_ict_signal(
    htf_candles: list[dict],
    poi_candles: list[dict],
    entry_candles: list[dict],
    mode: str = "strict",
    symbol: str = "BTCUSD",
) -> dict:
    """
    Analyse completed candles in chronological order.

    Important:
    All supplied candles must already be completed.
    The engine should pass only candles closed by the signal time.

    Returns BUY_WATCH, SELL_WATCH or WAIT.
    Never submits orders.
    """

    if mode not in STRATEGY_MODES:
        return {
            "signal": "WAIT",
            "reason": "Mode must be strict or balanced",
            "live_orders_enabled": False,
        }

    try:
        htf = _validate_candles(htf_candles)
        poi = _validate_candles(poi_candles)
        entry = _validate_candles(entry_candles)

        if len(htf) < MIN_HTF_CANDLES:
            return {
                "signal": "WAIT",
                "reason": "Need more completed 1H candles",
                "live_orders_enabled": False,
            }

        if len(poi) < MIN_POI_CANDLES:
            return {
                "signal": "WAIT",
                "reason": "Need more completed 15M candles",
                "live_orders_enabled": False,
            }

        if len(entry) < MIN_ENTRY_CANDLES:
            return {
                "signal": "WAIT",
                "reason": "Need more completed 5M candles",
                "live_orders_enabled": False,
            }

        # All functions now use the latest candle passed in.
        # Do not remove the latest candle again here.
        bias = _trend(htf)
        sweep = _liquidity_sweep(poi)
        shift = _structure_shift(entry)
        gap = _fvg(entry)
        displacement = _displacement(entry)

        settings = STRATEGY_MODES[mode]

        buy_checks = {
            "bullish_bias": bias["type"] == "BULLISH",
            "sell_side_sweep": sweep["type"] == "SELL_SIDE_SWEEP",
            "bullish_shift": shift["type"] == "BULLISH",
            "fvg": (
                not settings["require_fvg"]
                or gap["type"] == "BULLISH"
            ),
            "displacement": (
                not settings["require_displacement"]
                or displacement["detected"]
            ),
        }

        sell_checks = {
            "bearish_bias": bias["type"] == "BEARISH",
            "buy_side_sweep": sweep["type"] == "BUY_SIDE_SWEEP",
            "bearish_shift": shift["type"] == "BEARISH",
            "fvg": (
                not settings["require_fvg"]
                or gap["type"] == "BEARISH"
            ),
            "displacement": (
                not settings["require_displacement"]
                or displacement["detected"]
            ),
        }

        buy_ready = all(buy_checks.values())
        sell_ready = all(sell_checks.values())

        common = {
            "symbol": symbol,
            "mode": mode,
            "bias_1h": bias["type"],
            "bias_details": bias,
            "sweep_15m": sweep,
            "structure_5m": shift,
            "fvg_5m": gap,
            "displacement": displacement["detected"],
            "displacement_details": displacement,
            "buy_checks": buy_checks,
            "sell_checks": sell_checks,
            "live_orders_enabled": LIVE_ORDERS_ENABLED,
        }

        if buy_ready:
            return {
                **common,
                "signal": "BUY_WATCH",
                "reason": (
                    "All configured bullish conditions are aligned"
                ),
            }

        if sell_ready:
            return {
                **common,
                "signal": "SELL_WATCH",
                "reason": (
                    "All configured bearish conditions are aligned"
                ),
            }

        failed_buy = [
            key for key, passed in buy_checks.items() if not passed
        ]
        failed_sell = [
            key for key, passed in sell_checks.items() if not passed
        ]

        return {
            **common,
            "signal": "WAIT",
            "reason": "Setup conditions not aligned",
            "failed_buy_conditions": failed_buy,
            "failed_sell_conditions": failed_sell,
        }

    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return {
            "signal": "WAIT",
            "reason": f"Invalid candle data: {exc}",
            "live_orders_enabled": LIVE_ORDERS_ENABLED,
        }
