
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import isfinite
from typing import Any

from ict_strategy import detect_ict_signal


LIVE_ORDERS_ENABLED = False

TIMEFRAME_SECONDS = {
    "1h": 3600,
    "15m": 900,
    "5m": 300,
}

DEFAULT_SETTINGS = {
    "initial_balance": 1000.0,
    "position_size": 1.0,
    "take_profit_points": 20.0,
    "stop_loss_points": 15.0,
    "fee_rate": 0.0005,
    "slippage_points": 0.0,
    "point_value": 1.0,
}


@dataclass
class Trade:
    side: str
    entry: float
    exit: float
    size: float
    gross_pnl: float
    fees: float
    slippage_cost: float
    net_pnl: float
    result: str
    entry_time: int
    exit_time: int
    exit_reason: str


def _number(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be numeric") from None

    if not isfinite(result):
        raise ValueError(f"{name} must be finite")

    return result


def _validate(candles: list[dict], name: str) -> list[dict]:
    if not isinstance(candles, list):
        raise ValueError(f"{name} must be a list")

    result = []
    previous_time = None

    for i, candle in enumerate(candles):
        if not isinstance(candle, dict):
            raise ValueError(f"{name}[{i}] must be a dictionary")

        if "time" not in candle:
            raise ValueError(
                f"{name}[{i}] is missing 'time'; "
                "timestamp alignment is mandatory"
            )

        timestamp = int(_number(candle["time"], "time"))

        # This engine expects Unix timestamps in seconds.
        if timestamp < 1_000_000_000 or timestamp > 9_999_999_999:
            raise ValueError(
                "Candle time must be a Unix timestamp in seconds"
            )

        row = {
            "time": timestamp,
            "open": _number(candle["open"], "open"),
            "high": _number(candle["high"], "high"),
            "low": _number(candle["low"], "low"),
            "close": _number(candle["close"], "close"),
        }

        if row["high"] < max(row["open"], row["close"], row["low"]):
            raise ValueError(f"Invalid high in {name}[{i}]")

        if row["low"] > min(row["open"], row["close"], row["high"]):
            raise ValueError(f"Invalid low in {name}[{i}]")

        if previous_time is not None and timestamp <= previous_time:
            raise ValueError(
                f"{name} timestamps must be strictly increasing "
                "with no duplicates"
            )

        previous_time = timestamp
        result.append(row)

    return result


def _closed_before(
    candles: list[dict],
    timeframe: str,
    signal_time: int,
) -> list[dict]:
    """Only expose candles that closed by signal_time."""
    duration = TIMEFRAME_SECONDS[timeframe]

    return [
        candle for candle in candles
        if candle["time"] + duration <= signal_time
    ]


def _max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    maximum = 0.0

    for equity in equity_curve:
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)

    return maximum


def run_backtest(
    htf_candles: list[dict],
    poi_candles: list[dict],
    entry_candles: list[dict],
    symbol: str = "BTCUSD",
    mode: str = "strict",
    settings: dict | None = None,
) -> dict:
    """
    Historical-only backtest.

    All candle lists must be oldest-first and contain:
    time (Unix seconds), open, high, low, close.

    HTF = 1H; POI = 15M; entry = 5M.
    Signal is evaluated after a 5M candle closes.
    Entry occurs at the next 5M candle open.

    If TP and SL both touch in one candle, SL is assumed first.
    Open positions at the end remain open and are reported.
    This function never places exchange orders.
    """

    if mode not in ("strict", "balanced"):
        raise ValueError("mode must be 'strict' or 'balanced'")

    config = DEFAULT_SETTINGS.copy()
    if settings:
        config.update(settings)

    for key in DEFAULT_SETTINGS:
        config[key] = _number(config[key], key)

    if config["initial_balance"] <= 0:
        raise ValueError("initial_balance must be positive")

    if config["position_size"] <= 0 or config["point_value"] <= 0:
        raise ValueError("position_size and point_value must be positive")

    if config["take_profit_points"] <= 0:
        raise ValueError("take_profit_points must be positive")

    if config["stop_loss_points"] <= 0:
        raise ValueError("stop_loss_points must be positive")

    if config["fee_rate"] < 0 or config["slippage_points"] < 0:
        raise ValueError("Fees and slippage cannot be negative")

    htf = _validate(htf_candles, "htf_candles")
    poi = _validate(poi_candles, "poi_candles")
    entry = _validate(entry_candles, "entry_candles")

    if len(htf) < 30 or len(poi) < 25 or len(entry) < 31:
        raise ValueError(
            "Insufficient data: need at least 30 1H, "
            "25 15M and 31 5M candles"
        )

    balance = config["initial_balance"]
    equity_curve = [balance]
    trades: list[Trade] = []
    position = None

    for i in range(len(entry) - 1):
        candle = entry[i]
        candle_close_time = (
            candle["time"] + TIMEFRAME_SECONDS["5m"]
        )

        # Manage any open position using this completed candle.
        if position is not None:
            side = position["side"]
            sl = position["sl"]
            tp = position["tp"]

            if side == "BUY":
                hit_sl = candle["low"] <= sl
                hit_tp = candle["high"] >= tp
            else:
                hit_sl = candle["high"] >= sl
                hit_tp = candle["low"] <= tp

            if hit_sl or hit_tp:
                # Conservative same-candle assumption: SL first.
                reason = "SL" if hit_sl else "TP"
                raw_exit = sl if hit_sl else tp

                # Adverse exit slippage is applied once.
                exit_price = (
                    raw_exit - config["slippage_points"]
                    if side == "BUY"
                    else raw_exit + config["slippage_points"]
                )

                direction = 1.0 if side == "BUY" else -1.0
                size = config["position_size"]
                multiplier = config["point_value"]

                gross = (
                    (exit_price - position["entry"])
                    * direction * size * multiplier
                )

                # Fees are estimated on entry/exit notional.
                fees = (
                    abs(position["entry"]) + abs(exit_price)
                ) * size * multiplier * config["fee_rate"]

                slippage_cost = (
                    position["entry_slippage"]
                    + config["slippage_points"]
                ) * size * multiplier

                net = gross - fees
                balance += net

                trades.append(
                    Trade(
                        side=side,
                        entry=position["entry"],
                        exit=exit_price,
                        size=size,
                        gross_pnl=gross,
                        fees=fees,
                        slippage_cost=slippage_cost,
                        net_pnl=net,
                        result="WIN" if net > 0 else "LOSS",
                        entry_time=position["entry_time"],
                        exit_time=candle_close_time,
                        exit_reason=reason,
                    )
                )

                equity_curve.append(balance)
                position = None

        if position is not None:
            continue

        # Strategy only receives candles that have fully closed
        # by the signal timestamp. Timeframes are sliced separately.
        htf_available = _closed_before(
            htf, "1h", candle_close_time
        )
        poi_available = _closed_before(
            poi, "15m", candle_close_time
        )
        entry_available = entry[: i + 1]

        if (
            len(htf_available) < 30
            or len(poi_available) < 25
            or len(entry_available) < 31
        ):
            continue

        # ict_strategy expects OHLC keys; time can safely be omitted.
        signal = detect_ict_signal(
            htf_candles=[
                {k: c[k] for k in ("open", "high", "low", "close")}
                for c in htf_available
            ],
            poi_candles=[
                {k: c[k] for k in ("open", "high", "low", "close")}
                for c in poi_available
            ],
            entry_candles=[
                {k: c[k] for k in ("open", "high", "low", "close")}
                for c in entry_available
            ],
            mode=mode,
            symbol=symbol,
        )

        # Entry at the next candle's open, not the signal candle.
        next_candle = entry[i + 1]
        next_open = next_candle["open"]
        slip = config["slippage_points"]

        if signal.get("signal") == "BUY_WATCH":
            entry_price = next_open + slip
            position = {
                "side": "BUY",
                "entry": entry_price,
                "tp": entry_price + config["take_profit_points"],
                "sl": entry_price - config["stop_loss_points"],
                "entry_time": next_candle["time"],
                "entry_slippage": slip,
            }

        elif signal.get("signal") == "SELL_WATCH":
            entry_price = next_open - slip
            position = {
                "side": "SELL",
                "entry": entry_price,
                "tp": entry_price - config["take_profit_points"],
                "sl": entry_price + config["stop_loss_points"],
                "entry_time": next_candle["time"],
                "entry_slippage": slip,
            }

    wins = sum(t.net_pnl > 0 for t in trades)
    losses = sum(t.net_pnl <= 0 for t in trades)
    net_pnl = sum(t.net_pnl for t in trades)
    total_fees = sum(t.fees for t in trades)
    total_slippage = sum(t.slippage_cost for t in trades)

    gross_profit = sum(t.net_pnl for t in trades if t.net_pnl > 0)
    gross_loss = abs(sum(t.net_pnl for t in trades if t.net_pnl < 0))

    if gross_loss:
        profit_factor = gross_profit / gross_loss
    elif gross_profit:
        profit_factor = None  # Infinite; no losing trades in sample.
    else:
        profit_factor = 0.0

    return {
        "symbol": symbol,
        "mode": mode,
        "timeframes": {
            "direction": "1h",
            "poi": "15m",
            "entry": "5m",
        },
        "live_orders_enabled": LIVE_ORDERS_ENABLED,
        "initial_balance": config["initial_balance"],
        "final_balance_closed_trades_only": balance,
        "net_pnl_closed_trades_only": net_pnl,
        "return_percent_closed_trades_only": (
            net_pnl / config["initial_balance"] * 100
        ),
        "total_trades": len(trades),
        "winning_trades": wins,
        "losing_trades": losses,
        "win_rate_percent": (
            wins / len(trades) * 100 if trades else 0.0
        ),
        "profit_factor": profit_factor,
        "max_drawdown_closed_trades_only": _max_drawdown(equity_curve),
        "total_fees": total_fees,
        "estimated_slippage_cost": total_slippage,
        "open_position_at_end": position,
        "trades": [asdict(t) for t in trades],
        "warning": (
            "Prototype. Confirm exchange timestamp units, product "
            "multiplier, fee tier, funding and candle quality. "
            "Drawdown uses closed trades only and excludes unrealized P&L."
        ),
    }
