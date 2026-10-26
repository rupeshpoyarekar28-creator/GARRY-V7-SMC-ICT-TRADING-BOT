
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from ict_strategy import detect_ict_signal


# ============================================================
# GARRY V7 - HISTORICAL BACKTEST ENGINE
# Educational/testing only. No exchange orders are placed.
# ============================================================

LIVE_ORDERS_ENABLED = False

DEFAULT_SETTINGS = {
    "initial_balance": 1000.0,
    "position_size": 1.0,
    "take_profit_points": 20.0,
    "stop_loss_points": 15.0,
    "fee_rate": 0.0005,       # 0.05% per side; verify actual fee tier
    "slippage_points": 0.0,
    "point_value": 1.0,       # P&L currency per point per size unit
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
    entry_index: int
    exit_index: int
    exit_reason: str


def _float(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be numeric") from None

    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")

    return number


def _validate(candles: list[dict], name: str) -> list[dict]:
    if not isinstance(candles, list):
        raise ValueError(f"{name} must be a list")

    result = []

    for index, candle in enumerate(candles):
        if not isinstance(candle, dict):
            raise ValueError(f"{name}[{index}] must be a dictionary")

        row = {
            key: _float(candle[key], f"{name}[{index}].{key}")
            for key in ("open", "high", "low", "close")
        }

        if row["high"] < max(row["open"], row["close"], row["low"]):
            raise ValueError(f"Invalid high at {name}[{index}]")

        if row["low"] > min(row["open"], row["close"], row["high"]):
            raise ValueError(f"Invalid low at {name}[{index}]")

        result.append(row)

    return result


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]
    max_dd = 0.0

    for equity in equity_curve:
        peak = max(peak, equity)
        drawdown = peak - equity
        max_dd = max(max_dd, drawdown)

    return max_dd


def run_backtest(
    htf_candles: list[dict],
    poi_candles: list[dict],
    entry_candles: list[dict],
    symbol: str = "BTCUSD",
    mode: str = "strict",
    settings: dict | None = None,
) -> dict:
    """
    Run a simple historical backtest.

    IMPORTANT DATA CONTRACT:
    - All candle lists must be oldest-first.
    - Each list must contain completed candles only.
    - All three lists must be aligned by timestamp externally.
    - This first version expects aligned rows at matching indices.
    - No exchange API calls and no live orders are made.

    TP/SL use price points. If both TP and SL are touched in the
    same candle, the conservative assumption is that SL occurs first.
    """

    config = DEFAULT_SETTINGS.copy()

    if settings:
        config.update(settings)

    for key in (
        "initial_balance",
        "position_size",
        "take_profit_points",
        "stop_loss_points",
        "fee_rate",
        "slippage_points",
        "point_value",
    ):
        config[key] = _float(config[key], key)

    if config["initial_balance"] <= 0:
        raise ValueError("initial_balance must be positive")

    if config["position_size"] <= 0:
        raise ValueError("position_size must be positive")

    if config["take_profit_points"] <= 0 or config["stop_loss_points"] <= 0:
        raise ValueError("TP and SL must be positive")

    if config["fee_rate"] < 0 or config["slippage_points"] < 0:
        raise ValueError("Fees and slippage cannot be negative")

    if config["point_value"] <= 0:
        raise ValueError("point_value must be positive")

    htf = _validate(htf_candles, "htf_candles")
    poi = _validate(poi_candles, "poi_candles")
    entry = _validate(entry_candles, "entry_candles")

    n = min(len(htf), len(poi), len(entry))

    if n < 35:
        raise ValueError("Need at least 35 aligned rows per timeframe")

    balance = config["initial_balance"]
    equity_curve = [balance]
    trades: list[Trade] = []

    position = None

    # Begin after enough rows are available for the strategy.
    for i in range(30, n - 1):
        candle = entry[i]

        # Manage an existing position using the current completed candle.
        if position is not None:
            side = position["side"]
            tp = position["tp"]
            sl = position["sl"]

            if side == "BUY":
                hit_sl = candle["low"] <= sl
                hit_tp = candle["high"] >= tp

                if hit_sl or hit_tp:
                    if hit_sl:
                        raw_exit = sl
                        reason = "SL"
                    else:
                        raw_exit = tp
                        reason = "TP"

                    exit_price = raw_exit - config["slippage_points"]
                    gross = (
                        (exit_price - position["entry"])
                        * config["position_size"]
                        * config["point_value"]
                    )

                    entry_notional = (
                        position["entry"]
                        * config["position_size"]
                        * config["point_value"]
                    )
                    exit_notional = (
                        exit_price
                        * config["position_size"]
                        * config["point_value"]
                    )
                    fees = (
                        abs(entry_notional) + abs(exit_notional)
                    ) * config["fee_rate"]

                    slippage_cost = (
                        config["slippage_points"]
                        * config["position_size"]
                        * config["point_value"]
                    )

                    net = gross - fees
                    balance += net

                    trades.append(
                        Trade(
                            side=side,
                            entry=position["entry"],
                            exit=exit_price,
                            size=config["position_size"],
                            gross_pnl=gross,
                            fees=fees,
                            slippage_cost=slippage_cost,
                            net_pnl=net,
                            result="WIN" if net > 0 else "LOSS",
                            entry_index=position["entry_index"],
                            exit_index=i,
                            exit_reason=reason,
                        )
                    )

                    position = None

            else:
                hit_sl = candle["high"] >= sl
                hit_tp = candle["low"] <= tp

                if hit_sl or hit_tp:
                    if hit_sl:
                        raw_exit = sl
                        reason = "SL"
                    else:
                        raw_exit = tp
                        reason = "TP"

                    exit_price = raw_exit + config["slippage_points"]
                    gross = (
                        (position["entry"] - exit_price)
                        * config["position_size"]
                        * config["point_value"]
                    )

                    entry_notional = (
                        position["entry"]
                        * config["position_size"]
                        * config["point_value"]
                    )
                    exit_notional = (
                        exit_price
                        * config["position_size"]
                        * config["point_value"]
                    )
                    fees = (
                        abs(entry_notional) + abs(exit_notional)
                    ) * config["fee_rate"]

                    slippage_cost = (
                        config["slippage_points"]
                        * config["position_size"]
                        * config["point_value"]
                    )

                    net = gross - fees
                    balance += net

                    trades.append(
                        Trade(
                            side=side,
                            entry=position["entry"],
                            exit=exit_price,
                            size=config["position_size"],
                            gross_pnl=gross,
                            fees=fees,
                            slippage_cost=slippage_cost,
                            net_pnl=net,
                            result="WIN" if net > 0 else "LOSS",
                            entry_index=position["entry_index"],
                            exit_index=i,
                            exit_reason=reason,
                        )
                    )

                    position = None

        # If still in a trade, do not open another.
        if position is not None:
            equity_curve.append(balance)
            continue

        # Supply only candles available up to the current index.
        signal = detect_ict_signal(
            htf_candles=htf[: i + 1],
            poi_candles=poi[: i + 1],
            entry_candles=entry[: i + 1],
            mode=mode,
            symbol=symbol,
        )

        # Entry at the next candle open to avoid same-candle entry bias.
        next_open = entry[i + 1]["open"]

        if signal.get("signal") == "BUY_WATCH":
            entry_price = next_open + config["slippage_points"]
            position = {
                "side": "BUY",
                "entry": entry_price,
                "tp": entry_price + config["take_profit_points"],
                "sl": entry_price - config["stop_loss_points"],
                "entry_index": i + 1,
            }

        elif signal.get("signal") == "SELL_WATCH":
            entry_price = next_open - config["slippage_points"]
            position = {
                "side": "SELL",
                "entry": entry_price,
                "tp": entry_price - config["take_profit_points"],
                "sl": entry_price + config["stop_loss_points"],
                "entry_index": i + 1,
            }

        equity_curve.append(balance)

    wins = sum(1 for trade in trades if trade.net_pnl > 0)
    losses = sum(1 for trade in trades if trade.net_pnl <= 0)

    gross_profit = sum(
        trade.net_pnl for trade in trades if trade.net_pnl > 0
    )
    gross_loss = abs(
        sum(trade.net_pnl for trade in trades if trade.net_pnl < 0)
    )

    net_pnl = sum(trade.net_pnl for trade in trades)
    total_fees = sum(trade.fees for trade in trades)
    total_slippage = sum(trade.slippage_cost for trade in trades)

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else (float("inf") if gross_profit > 0 else 0.0)
    )

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
        "final_balance": balance,
        "net_pnl": net_pnl,
        "return_percent": (
            net_pnl / config["initial_balance"] * 100
        ),
        "total_trades": len(trades),
        "winning_trades": wins,
        "losing_trades": losses,
        "win_rate_percent": (
            wins / len(trades) * 100 if trades else 0.0
        ),
        "profit_factor": profit_factor,
        "max_drawdown": _max_drawdown(equity_curve),
        "total_fees": total_fees,
        "total_slippage_cost": total_slippage,
        "open_position_at_end": position,
        "trades": [asdict(trade) for trade in trades],
        "warning": (
            "Prototype only. Verify candle timestamp alignment, "
            "contract point value, exchange fees, funding, and "
            "data quality before trusting results."
        ),
    }
