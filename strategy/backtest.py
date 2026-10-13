
"""GARRY V7 — historical strategy backtesting.

Historical simulation only.
Never places exchange orders.
Includes estimated trading fees and conservative same-candle
stop-loss/take-profit handling.
"""

import math
import time
from datetime import datetime, timezone, timedelta

from data.delta_public import (
    APPROVED_SYMBOLS,
    DeltaPublicClient,
    DeltaAPIError,
)


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
}

# Approximate taker fee per side. Verify against your exchange fee tier.
DEFAULT_FEE_RATE = 0.0005
DEFAULT_RISK_REWARD = 2.0
DEFAULT_LOOKBACK = 20


def _number(row, *keys):
    for key in keys:
        value = row.get(key)
        try:
            number = float(value)
            if math.isfinite(number):
                return number
        except (TypeError, ValueError, OverflowError):
            pass
    return None


def _parse_candles(payload):
    """Normalize common Delta candle response formats."""
    if not isinstance(payload, dict):
        raise DeltaAPIError("Invalid historical candle response.")

    if payload.get("success") is False:
        raise DeltaAPIError("Delta rejected historical candle request.")

    rows = payload.get("result", payload.get("data", []))
    if not isinstance(rows, list):
        raise DeltaAPIError("Historical candle result is not a list.")

    candles = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        timestamp = _number(row, "time", "timestamp", "t")
        open_price = _number(row, "open", "o")
        high = _number(row, "high", "h")
        low = _number(row, "low", "l")
        close = _number(row, "close", "c")
        volume = _number(row, "volume", "v") or 0.0

        if None in (timestamp, open_price, high, low, close):
            continue
        if min(open_price, high, low, close) <= 0:
            continue
        if high < low or high < max(open_price, close):
            continue
        if low > min(open_price, close):
            continue

        candles.append({
            "time": int(timestamp),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })

    # De-duplicate and sort chronologically.
    unique = {candle["time"]: candle for candle in candles}
    return [unique[t] for t in sorted(unique)]


def _fetch_candles(symbol, resolution, days, client=None):
    if symbol not in APPROVED_SYMBOLS:
        raise ValueError("Market is not in the approved symbol list.")
    if resolution not in RESOLUTION_SECONDS:
        raise ValueError("Unsupported timeframe.")
    if not 1 <= int(days) <= 90:
        raise ValueError("Backtest history must be between 1 and 90 days.")

    client = client or DeltaPublicClient(timeout=10)

    end = int(time.time())
    start = end - int(days) * 86400

    # Delta history endpoints may limit candles per request.
    # Split the date range into smaller windows.
    step = min(
        5 * 86400,
        RESOLUTION_SECONDS[resolution] * 800,
    )
    all_rows = []

    cursor = start
    while cursor < end:
        window_end = min(cursor + step, end)
        payload = client.get_recent_candles(
            symbol=symbol,
            resolution=resolution,
            start=cursor,
            end=window_end,
        )
        all_rows.extend(_parse_candles(payload))
        cursor = window_end

    candles = _parse_candles({"result": all_rows})
    if len(candles) < DEFAULT_LOOKBACK + 5:
        raise ValueError(
            f"Not enough candles returned ({len(candles)}). "
            "Check API availability, timeframe and selected history."
        )

    return candles


def _calculate_drawdown(equity_values):
    peak = 0.0
    max_drawdown = 0.0

    for equity in equity_values:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, peak - equity)

    return max_drawdown


def run_backtest(
    symbol="BTCUSD",
    resolution="5m",
    days=30,
    initial_capital=10000.0,
    risk_per_trade=0.01,
    fee_rate=DEFAULT_FEE_RATE,
    risk_reward=DEFAULT_RISK_REWARD,
    lookback=DEFAULT_LOOKBACK,
    client=None,
):
    """Run a historical BOS-style breakout simulation.

    Rules:
    - Long: close breaks above the previous lookback highs.
    - Short: close breaks below the previous lookback lows.
    - Stop: opposite extreme of the lookback window.
    - Target: configured risk/reward multiple.
    - Position size: fixed fraction of current simulated equity.
    - One position at a time; no pyramiding.
    - If SL and TP are both touched in one candle, assume SL first.
    - Entry occurs at the signal candle close; fees charged on entry/exit.
    """

    symbol = str(symbol).upper().strip()
    resolution = str(resolution).strip()
    days = int(days)
    initial_capital = float(initial_capital)
    risk_per_trade = float(risk_per_trade)
    fee_rate = float(fee_rate)
    risk_reward = float(risk_reward)
    lookback = int(lookback)

    if initial_capital <= 0:
        raise ValueError("Initial capital must be positive.")
    if not 0 < risk_per_trade <= 0.05:
        raise ValueError("Risk per trade must be between 0 and 5%.")
    if not 0 <= fee_rate < 0.1:
        raise ValueError("Invalid fee rate.")
    if risk_reward <= 0:
        raise ValueError("Risk/reward must be positive.")
    if not 5 <= lookback <= 200:
        raise ValueError("Lookback must be between 5 and 200 candles.")

    candles = _fetch_candles(
        symbol=symbol,
        resolution=resolution,
        days=days,
        client=client,
    )

    equity = initial_capital
    equity_curve = [equity]
    trades = []
    position = None

    for index in range(lookback, len(candles)):
        candle = candles[index]
        previous = candles[index - lookback:index]

        # Resolve an existing position before considering a new signal.
        if position is not None:
            exit_price = None
            exit_reason = None

            if position["side"] == "LONG":
                stop_hit = candle["low"] <= position["stop"]
                target_hit = candle["high"] >= position["target"]

                if stop_hit:
                    exit_price, exit_reason = position["stop"], "SL"
                elif target_hit:
                    exit_price, exit_reason = position["target"], "TP"
            else:
                stop_hit = candle["high"] >= position["stop"]
                target_hit = candle["low"] <= position["target"]

                if stop_hit:
                    exit_price, exit_reason = position["stop"], "SL"
                elif target_hit:
                    exit_price, exit_reason = position["target"], "TP"

            if exit_price is not None:
                quantity = position["quantity"]
                gross = (
                    (exit_price - position["entry"]) * quantity
                    if position["side"] == "LONG"
                    else (position["entry"] - exit_price) * quantity
                )
                exit_fee = abs(exit_price * quantity) * fee_rate
                net = gross - position["entry_fee"] - exit_fee
                equity += net

                trades.append({
                    "side": position["side"],
                    "entry_time": position["entry_time"],
                    "exit_time": candle["time"],
                    "entry": round(position["entry"], 8),
                    "exit": round(exit_price, 8),
                    "stop": round(position["stop"], 8),
                    "target": round(position["target"], 8),
                    "quantity": round(quantity, 8),
                    "gross_pnl": round(gross, 4),
                    "fees": round(position["entry_fee"] + exit_fee, 4),
                    "net_pnl": round(net, 4),
                    "exit_reason": exit_reason,
                })
                position = None
                equity_curve.append(equity)

        if position is not None or equity <= 0:
            continue

        prior_high = max(item["high"] for item in previous)
        prior_low = min(item["low"] for item in previous)
        entry = candle["close"]

        if entry > prior_high:
            side = "LONG"
            stop = prior_low
        elif entry < prior_low:
            side = "SHORT"
            stop = prior_high
        else:
            continue

        risk_distance = abs(entry - stop)
        if risk_distance <= 0:
            continue

        target = (
            entry + risk_distance * risk_reward
            if side == "LONG"
            else entry - risk_distance * risk_reward
        )
        if target <= 0:
            continue

        risk_cash = equity * risk_per_trade
        quantity = risk_cash / risk_distance
        entry_fee = abs(entry * quantity) * fee_rate

        # Do not open a trade if the estimated entry fee alone exceeds
        # 10% of the intended risk budget.
        if entry_fee > risk_cash * 0.10:
            continue

        position = {
            "side": side,
            "entry_time": candle["time"],
            "entry": entry,
            "stop": stop,
            "target": target,
            "quantity": quantity,
            "entry_fee": entry_fee,
        }

    # Close any open position at the last available candle close.
    if position is not None:
        last = candles[-1]
        exit_price = last["close"]
        quantity = position["quantity"]
        gross = (
            (exit_price - position["entry"]) * quantity
            if position["side"] == "LONG"
            else (position["entry"] - exit_price) * quantity
        )
        exit_fee = abs(exit_price * quantity) * fee_rate
        net = gross - position["entry_fee"] - exit_fee
        equity += net

        trades.append({
            "side": position["side"],
            "entry_time": position["entry_time"],
            "exit_time": last["time"],
            "entry": round(position["entry"], 8),
            "exit": round(exit_price, 8),
            "stop": round(position["stop"], 8),
            "target": round(position["target"], 8),
            "quantity": round(quantity, 8),
            "gross_pnl": round(gross, 4),
            "fees": round(position["entry_fee"] + exit_fee, 4),
            "net_pnl": round(net, 4),
            "exit_reason": "END_OF_DATA",
        })
        equity_curve.append(equity)

    wins = [trade for trade in trades if trade["net_pnl"] > 0]
    losses = [trade for trade in trades if trade["net_pnl"] < 0]
    gross_profit = sum(trade["net_pnl"] for trade in wins)
    gross_loss = abs(sum(trade["net_pnl"] for trade in losses))
    net_pnl = equity - initial_capital

    profit_factor = (
        round(gross_profit / gross_loss, 4)
        if gross_loss > 0
        else ("INF" if gross_profit > 0 else 0.0)
    )

    return {
        "symbol": symbol,
        "timeframe": resolution,
        "days_requested": days,
        "candles": len(candles),
        "first_candle_utc": datetime.fromtimestamp(
            candles[0]["time"], timezone.utc
        ).isoformat(),
        "last_candle_utc": datetime.fromtimestamp(
            candles[-1]["time"], timezone.utc
        ).isoformat(),
        "initial_capital": round(initial_capital, 2),
        "ending_equity": round(equity, 2),
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": round(100 * len(wins) / len(trades), 2) if trades else 0.0,
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "net_pnl": round(net_pnl, 2),
        "profit_factor": profit_factor,
        "max_drawdown": round(_calculate_drawdown(equity_curve), 2),
        "max_drawdown_percent": round(
            100 * _calculate_drawdown(equity_curve) / initial_capital, 2
        ),
        "fee_rate_per_side": fee_rate,
        "risk_per_trade_percent": round(risk_per_trade * 100, 2),
        "risk_reward": risk_reward,
        "trades": trades,
        "strategy": "Lookback breakout with swing-window stop",
        "execution_mode": "HISTORICAL SIMULATION ONLY",
    }
