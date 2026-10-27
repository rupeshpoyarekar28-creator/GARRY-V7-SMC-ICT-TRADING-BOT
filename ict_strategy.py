from __future__ import annotations
from math import isfinite
from typing import Any

LIVE_ORDERS_ENABLED = False
MIN_HTF_CANDLES = 40
MIN_POI_CANDLES = 25
MIN_ENTRY_CANDLES = 31
TREND_WINDOW = 20
LIQUIDITY_LOOKBACK = 10
RECENT_SWEEP_CANDLES = 4
STRUCTURE_LOOKBACK = 10
FVG_LOOKBACK = 10
DISPLACEMENT_LOOKBACK = 10

STRATEGY_MODES = {
    "strict": {"require_fvg": True, "require_displacement": True},
    "balanced": {"require_fvg": False, "require_displacement": False},
}

def _number(value: Any) -> float:
    result = float(value)
    if not isfinite(result):
        raise ValueError("Non-finite candle value")
    return result

def _validate_candles(candles: list[dict], name: str) -> list[dict]:
    if not isinstance(candles, list):
        raise ValueError(f"{name} must be a list")
    cleaned, previous_time = [], None
    for i, candle in enumerate(candles):
        if not isinstance(candle, dict):
            raise ValueError(f"{name}[{i}] must be a dictionary")
        row = {k: _number(candle[k]) for k in ("open", "high", "low", "close")}
        if row["high"] < max(row["open"], row["close"], row["low"]):
            raise ValueError(f"Invalid high in {name}[{i}]")
        if row["low"] > min(row["open"], row["close"], row["high"]):
            raise ValueError(f"Invalid low in {name}[{i}]")
        if "time" in candle:
            t = int(_number(candle["time"]))
            if previous_time is not None and t <= previous_time:
                raise ValueError(f"{name} times must be strictly increasing")
            row["time"] = t
            previous_time = t
        cleaned.append(row)
    return cleaned

def _trend(candles: list[dict]) -> dict:
    if len(candles) < 40:
        return {"type": "NEUTRAL", "reason": "Need 40 completed 1H candles"}
    earlier, recent = candles[-40:-20], candles[-20:]
    eh, el = max(c["high"] for c in earlier), min(c["low"] for c in earlier)
    rh, rl = max(c["high"] for c in recent), min(c["low"] for c in recent)
    if rh > eh and rl > el:
        return {"type": "BULLISH", "reason": "Recent 1H range high and low are higher"}
    if rh < eh and rl < el:
        return {"type": "BEARISH", "reason": "Recent 1H range high and low are lower"}
    return {"type": "NEUTRAL", "reason": "1H range structure is mixed"}

def _find_sweep(candles: list[dict]) -> dict:
    if len(candles) < LIQUIDITY_LOOKBACK + 1:
        return {"type": "NONE", "level": None, "time": None, "reason": "Insufficient 15M candles"}
    start = max(LIQUIDITY_LOOKBACK, len(candles) - RECENT_SWEEP_CANDLES)
    for i in range(len(candles) - 1, start - 1, -1):
        cur = candles[i]
        ref = candles[i-LIQUIDITY_LOOKBACK:i]
        hi, lo = max(c["high"] for c in ref), min(c["low"] for c in ref)
        if cur["high"] > hi and cur["close"] < hi:
            return {"type": "BUY_SIDE_SWEEP", "level": hi, "time": cur.get("time"),
                    "reason": "Swept prior highs and closed below"}
        if cur["low"] < lo and cur["close"] > lo:
            return {"type": "SELL_SIDE_SWEEP", "level": lo, "time": cur.get("time"),
                    "reason": "Swept prior lows and closed above"}
    return {"type": "NONE", "level": None, "time": None,
            "reason": "No sweep in recent completed 15M candles"}

def _structure_shift(candles: list[dict]) -> dict:
    if len(candles) < STRUCTURE_LOOKBACK + 1:
        return {"type": "NONE", "level": None, "time": None, "reason": "Insufficient 5M candles"}
    cur, ref = candles[-1], candles[-STRUCTURE_LOOKBACK-1:-1]
    hi, lo = max(c["high"] for c in ref), min(c["low"] for c in ref)
    if cur["close"] > hi:
        return {"type": "BULLISH", "level": hi, "time": cur.get("time"), "reason": "5M close broke prior range high"}
    if cur["close"] < lo:
        return {"type": "BEARISH", "level": lo, "time": cur.get("time"), "reason": "5M close broke prior range low"}
    return {"type": "NONE", "level": None, "time": cur.get("time"), "reason": "No 5M close beyond prior range"}

def _fvg(candles: list[dict]) -> dict:
    if len(candles) < 3:
        return {"type": "NONE", "low": None, "high": None, "reason": "Insufficient candles"}
    start = max(2, len(candles) - FVG_LOOKBACK)
    for i in range(len(candles)-1, start-1, -1):
        first, third = candles[i-2], candles[i]
        if third["low"] > first["high"]:
            return {"type": "BULLISH", "low": first["high"], "high": third["low"], "reason": "Bullish three-candle gap"}
        if third["high"] < first["low"]:
            return {"type": "BEARISH", "low": third["high"], "high": first["low"], "reason": "Bearish three-candle gap"}
    return {"type": "NONE", "low": None, "high": None, "reason": "No recent FVG"}

def _displacement(candles: list[dict]) -> dict:
    n = DISPLACEMENT_LOOKBACK + 1
    if len(candles) < n:
        return {"detected": False, "direction": "NONE", "body": None, "average_body": None, "reason": "Insufficient candles"}
    cur = candles[-1]
    body = abs(cur["close"] - cur["open"])
    bodies = [abs(c["close"] - c["open"]) for c in candles[-n:-1]]
    avg = sum(bodies) / len(bodies)
    detected = avg > 0 and body >= 1.5 * avg
    direction = "BULLISH" if cur["close"] > cur["open"] else ("BEARISH" if cur["close"] < cur["open"] else "NONE")
    return {"detected": detected, "direction": direction, "body": body, "average_body": avg,
            "reason": "Body expansion detected" if detected else "Body below 1.5x average"}

def detect_ict_signal(htf_candles: list[dict], poi_candles: list[dict],
                      entry_candles: list[dict], mode: str = "strict",
                      symbol: str = "BTCUSD") -> dict:
    base = {"signal": "WAIT", "symbol": symbol, "mode": mode, "live_orders_enabled": False}
    if mode not in STRATEGY_MODES:
        return {**base, "reason": "Mode must be strict or balanced"}
    try:
        htf = _validate_candles(htf_candles, "htf_candles")
        poi = _validate_candles(poi_candles, "poi_candles")
        entry = _validate_candles(entry_candles, "entry_candles")
        if len(htf) < MIN_HTF_CANDLES:
            return {**base, "reason": "Need at least 40 completed 1H candles"}
        if len(poi) < MIN_POI_CANDLES:
            return {**base, "reason": "Need at least 25 completed 15M candles"}
        if len(entry) < MIN_ENTRY_CANDLES:
            return {**base, "reason": "Need at least 31 completed 5M candles"}
        bias, sweep = _trend(htf), _find_sweep(poi)
        shift, gap, disp = _structure_shift(entry), _fvg(entry), _displacement(entry)
        # Require sweep candle timestamp not to be later than the 5M shift candle.
        sequence_ok = True
        if sweep.get("time") is not None and shift.get("time") is not None:
            sequence_ok = sweep["time"] <= shift["time"]
        cfg = STRATEGY_MODES[mode]
        buy = {
            "bullish_bias": bias["type"] == "BULLISH",
            "sell_side_sweep": sweep["type"] == "SELL_SIDE_SWEEP",
            "sweep_before_shift": sequence_ok,
            "bullish_shift": shift["type"] == "BULLISH",
            "fvg": not cfg["require_fvg"] or gap["type"] == "BULLISH",
            "bullish_displacement": not cfg["require_displacement"] or (disp["detected"] and disp["direction"] == "BULLISH"),
        }
        sell = {
            "bearish_bias": bias["type"] == "BEARISH",
            "buy_side_sweep": sweep["type"] == "BUY_SIDE_SWEEP",
            "sweep_before_shift": sequence_ok,
            "bearish_shift": shift["type"] == "BEARISH",
            "fvg": not cfg["require_fvg"] or gap["type"] == "BEARISH",
            "bearish_displacement": not cfg["require_displacement"] or (disp["detected"] and disp["direction"] == "BEARISH"),
        }
        common = {**base, "bias_1h": bias["type"], "bias_details": bias, "sweep_15m": sweep,
                  "structure_5m": shift, "fvg_5m": gap, "displacement": disp["detected"],
                  "displacement_details": disp, "buy_checks": buy, "sell_checks": sell}
        if all(buy.values()):
            return {**common, "signal": "BUY_WATCH", "reason": "Bullish conditions aligned"}
        if all(sell.values()):
            return {**common, "signal": "SELL_WATCH", "reason": "Bearish conditions aligned"}
        return {**common, "reason": "Setup conditions not aligned",
                "failed_buy_conditions": [k for k,v in buy.items() if not v],
                "failed_sell_conditions": [k for k,v in sell.items() if not v]}
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return {**base, "reason": f"Invalid candle data: {exc}"}
