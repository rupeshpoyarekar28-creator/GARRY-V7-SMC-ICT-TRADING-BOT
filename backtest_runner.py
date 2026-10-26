
from __future__ import annotations

import os
import requests
from datetime import datetime, timezone
from typing import Any


# ============================================================
# GARRY V7 - HISTORICAL DATA RUNNER
# Data download and validation only.
# No live trading and no exchange orders.
# ============================================================

DASHBOARD_URL = os.getenv(
    "GARRY_DASHBOARD_URL",
    "https://garry-v7-smc-ict-trading-bot.onrender.com",
).rstrip("/")

REQUEST_TIMEOUT = 20
LIVE_ORDERS_ENABLED = False

RESOLUTION_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "1d": 86400,
    "1w": 604800,
}


class BacktestDataError(Exception):
    """Raised when historical market data is invalid or unavailable."""


def fetch_candles(
    symbol: str,
    resolution: str,
    start: int,
    end: int,
) -> list[dict[str, Any]]:
    """Fetch candles through the existing GARRY V7 dashboard API."""

    if resolution not in RESOLUTION_SECONDS:
        raise BacktestDataError(
            f"Unsupported resolution: {resolution}"
        )

    if start >= end:
        raise BacktestDataError("Start timestamp must be before end")

    url = f"{DASHBOARD_URL}/api/candles"

    try:
        response = requests.get(
            url,
            params={
                "symbol": symbol.upper(),
                "resolution": resolution,
                "start": int(start),
                "end": int(end),
            },
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()

    except requests.RequestException as exc:
        raise BacktestDataError(
            f"Could not download {symbol} {resolution} candles: {exc}"
        ) from exc

    except ValueError as exc:
        raise BacktestDataError(
            "Dashboard returned invalid JSON"
        ) from exc

    if payload.get("ok") is not True:
        raise BacktestDataError(
            payload.get("error", "Historical API request failed")
        )

    candles = payload.get("candles")

    if not isinstance(candles, list):
        raise BacktestDataError(
            "API response did not contain a candle list"
        )

    cleaned = []

    for candle in candles:
        if not isinstance(candle, dict):
            continue

        # Delta candle responses normally include time and OHLC.
        timestamp = candle.get("time", candle.get("timestamp"))

        if timestamp is None:
            raise BacktestDataError(
                "Candle timestamp missing; cannot safely align timeframes"
            )

        try:
            timestamp = int(timestamp)
            row = {
                "time": timestamp,
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
            }
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise BacktestDataError(
                "Candle contains missing or invalid OHLC data"
            ) from exc

        if not all(
            value == value and abs(value) != float("inf")
            for value in (
                row["open"],
                row["high"],
                row["low"],
                row["close"],
            )
        ):
            raise BacktestDataError("Non-finite OHLC value")

        if (
            row["high"] < max(row["open"], row["close"], row["low"])
            or row["low"] > min(row["open"], row["close"], row["high"])
        ):
            raise BacktestDataError("Invalid OHLC candle")

        # Exclude candles outside the requested interval.
        if start <= timestamp < end:
            cleaned.append(row)

    cleaned.sort(key=lambda candle: candle["time"])

    # Remove duplicate timestamps.
    unique = []
    seen = set()

    for candle in cleaned:
        if candle["time"] not in seen:
            unique.append(candle)
            seen.add(candle["time"])

    return unique


def align_timeframes(
    htf: list[dict],
    poi: list[dict],
    entry: list[dict],
) -> list[dict]:
    """
    Build entry-time rows with the latest COMPLETED HTF and POI
    candles available at each entry timestamp.

    This avoids matching unrelated rows merely by list index.
    Input candles must contain Unix timestamps in seconds.
    """

    if not htf or not poi or not entry:
        raise BacktestDataError("One or more timeframes contain no data")

    htf = sorted(htf, key=lambda c: c["time"])
    poi = sorted(poi, key=lambda c: c["time"])
    entry = sorted(entry, key=lambda c: c["time"])

    aligned = []
    htf_index = 0
    poi_index = 0
    latest_htf = None
    latest_poi = None

    for entry_candle in entry:
        entry_time = int(entry_candle["time"])

        # A candle is usable only after its timeframe has closed.
        while htf_index < len(htf):
            candle = htf[htf_index]
            close_time = candle["time"] + RESOLUTION_SECONDS["1h"]

            if close_time > entry_time:
                break

            latest_htf = candle
            htf_index += 1

        while poi_index < len(poi):
            candle = poi[poi_index]
            close_time = candle["time"] + RESOLUTION_SECONDS["15m"]

            if close_time > entry_time:
                break

            latest_poi = candle
            poi_index += 1

        if latest_htf is None or latest_poi is None:
            continue

        aligned.append({
            "time": entry_time,
            "htf": latest_htf,
            "poi": latest_poi,
            "entry": entry_candle,
        })

    if not aligned:
        raise BacktestDataError(
            "No aligned rows. Check timestamp units and data range."
        )

    return aligned


def inspect_data(
    symbol: str,
    start: int,
    end: int,
) -> dict:
    """Download and validate data; does not run trades."""

    htf = fetch_candles(symbol, "1h", start, end)
    poi = fetch_candles(symbol, "15m", start, end)
    entry = fetch_candles(symbol, "5m", start, end)

    aligned = align_timeframes(htf, poi, entry)

    return {
        "symbol": symbol.upper(),
        "start_utc": datetime.fromtimestamp(
            start, tz=timezone.utc
        ).isoformat(),
        "end_utc": datetime.fromtimestamp(
            end, tz=timezone.utc
        ).isoformat(),
        "candles_1h": len(htf),
        "candles_15m": len(poi),
        "candles_5m": len(entry),
        "aligned_rows": len(aligned),
        "live_orders_enabled": LIVE_ORDERS_ENABLED,
        "status": "DATA_VALIDATED_ONLY",
        "note": (
            "This function validates data only. It does not call "
            "the backtest engine or place orders."
        ),
    }


if __name__ == "__main__":
    print(
        "GARRY V7 backtest data runner loaded. "
        "Call inspect_data(symbol, start, end) from a test script."
    )
