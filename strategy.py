
def detect_signal(candles: list[dict]) -> dict:
    """
    Educational SMC prototype.
    Uses completed OHLC candles only.
    Does not place orders.
    """
    required = ("open", "high", "low", "close")

    if not isinstance(candles, list) or len(candles) < 30:
        return {
            "signal": "WAIT",
            "reason": "Need at least 30 completed candles"
        }

    try:
        for candle in candles:
            for key in required:
                value = float(candle[key])
                if not __import__("math").isfinite(value):
                    raise ValueError("Non-finite candle value")

            if float(candle["high"]) < float(candle["low"]):
                raise ValueError("Invalid candle high/low")

        data = candles[:-1]
        current = candles[-1]

        highs = [float(c["high"]) for c in data]
        lows = [float(c["low"]) for c in data]
        close = float(current["close"])
        high = float(current["high"])
        low = float(current["low"])

        # Reference range from the previous 20 candles
        reference_high = max(highs[-20:])
        reference_low = min(lows[-20:])

        # Liquidity sweep and close back inside the range
        if high > reference_high and close < reference_high:
            return {
                "signal": "SELL_WATCH",
                "reason": "Potential buy-side liquidity sweep",
                "reference_level": reference_high,
                "close": close
            }

        if low < reference_low and close > reference_low:
            return {
                "signal": "BUY_WATCH",
                "reason": "Potential sell-side liquidity sweep",
                "reference_level": reference_low,
                "close": close
            }

        # Breakout confirmation
        if close > reference_high:
            return {
                "signal": "BULLISH_BREAKOUT",
                "reason": "Close above previous 20-candle high",
                "reference_level": reference_high,
                "close": close
            }

        if close < reference_low:
            return {
                "signal": "BEARISH_BREAKOUT",
                "reason": "Close below previous 20-candle low",
                "reference_level": reference_low,
                "close": close
            }

        return {
            "signal": "WAIT",
            "reason": "No qualifying setup",
            "reference_high": reference_high,
            "reference_low": reference_low,
            "close": close
        }

    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return {
            "signal": "WAIT",
            "reason": f"Invalid candle data: {exc}"
        }
