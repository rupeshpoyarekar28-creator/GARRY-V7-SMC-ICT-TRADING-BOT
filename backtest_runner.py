
from __future__ import annotations

import json
import os
import time
import requests

from backtest_engine import run_backtest


DASHBOARD_URL = os.getenv(
    "GARRY_DASHBOARD_URL",
    "https://garry-v7-smc-ict-trading-bot.onrender.com",
).rstrip("/")

TIMEOUT = 25

RESOLUTIONS = {
    "1h": 3600,
    "15m": 900,
    "5m": 300,
}

LIVE_ORDERS_ENABLED = False


def fetch_candles(symbol: str, resolution: str,
                  start: int, end: int) -> list[dict]:
    url = f"{DASHBOARD_URL}/api/candles"

    response = requests.get(
        url,
        params={
            "symbol": symbol,
            "resolution": resolution,
            "start": start,
            "end": end,
        },
        timeout=TIMEOUT,
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    payload = response.json()

    if payload.get("ok") is not True:
        raise RuntimeError(
            payload.get("error", "Historical data request failed")
        )

    rows = []
    duration = RESOLUTIONS[resolution]

    for c in payload.get("candles", []):
        timestamp = int(c.get("time", c.get("timestamp", 0)))

        # Only use candles fully closed by the requested end time.
        if timestamp <= 0 or timestamp + duration > end:
            continue

        rows.append({
            "time": timestamp,
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
        })

    rows.sort(key=lambda c: c["time"])

    deduplicated = []
    seen = set()

    for row in rows:
        if row["time"] not in seen:
            deduplicated.append(row)
            seen.add(row["time"])

    if len(deduplicated) < 35:
        raise RuntimeError(
            f"Not enough {resolution} candles returned: "
            f"{len(deduplicated)}"
        )

    return deduplicated


def run_historical_test(
    symbol: str = "BTCUSD",
    days: int = 30,
) -> dict:
    """
    Run a historical test only.
    All timeframes use the same UTC timestamp window.
    """

    if symbol not in ("BTCUSD", "XAUTUSD"):
        raise ValueError(
            "Only BTCUSD and XAUTUSD are configured. "
            "Verify the exact Gold futures contract before using it."
        )

    if days < 2 or days > 180:
        raise ValueError("days must be between 2 and 180")

    end = int(time.time())
    start = end - days * 86400

    htf = fetch_candles(symbol, "1h", start, end)
    poi = fetch_candles(symbol, "15m", start, end)
    entry = fetch_candles(symbol, "5m", start, end)

    # Important: engine validates timestamp presence and order.
    # It also uses closed higher-timeframe candles for signals.
    results = {}

    for mode in ("strict", "balanced"):
        results[mode] = run_backtest(
            htf_candles=htf,
            poi_candles=poi,
            entry_candles=entry,
            symbol=symbol,
            mode=mode,
        )

    return {
        "status": "HISTORICAL_BACKTEST_COMPLETE",
        "symbol": symbol,
        "days_requested": days,
        "live_orders_enabled": LIVE_ORDERS_ENABLED,
        "candles": {
            "1h": len(htf),
            "15m": len(poi),
            "5m": len(entry),
        },
        "results": results,
        "warning": (
            "Prototype only. Check the exchange's actual contract "
            "specification, fee tier, funding and point value. "
            "XAUTUSD is not assumed to be a Gold futures contract."
        ),
    }


if __name__ == "__main__":
    # Small first run. No real orders are submitted.
    try:
        report = run_historical_test(
            symbol=os.getenv("BACKTEST_SYMBOL", "BTCUSD"),
            days=int(os.getenv("BACKTEST_DAYS", "7")),
        )
        print(json.dumps(report, indent=2, allow_nan=False))
    except Exception as exc:
        print(json.dumps({
            "status": "BACKTEST_FAILED",
            "error": str(exc),
            "live_orders_enabled": LIVE_ORDERS_ENABLED,
        }, indent=2))
