from collections import defaultdict
from math import isfinite

from ict_strategy import detect_ict_signal

LIVE_ORDERS_ENABLED = False

DEFAULT_SETTINGS = {
    "initial_balance_usd": 100.0,
    "lot_size": 0.03,
    "contract_size_oz_per_lot": 10.0,
    "take_profit_price": 20.0,
    "stop_loss_price": 15.0,
    "max_trades_per_day": 4,
    "fee_rate_per_side": 0.0005,
    "slippage_price": 0.0,
}


def validate_candles(candles, name, seconds):
    if not isinstance(candles, list):
        raise ValueError(f"{name} must be a list")

    result = []
    previous = None

    for row in candles:
        candle = {"time": int(row["time"])}

        for key in ("open", "high", "low", "close"):
            value = float(row[key])
            if not isfinite(value):
                raise ValueError("Invalid candle value")
            candle[key] = value

        if candle["high"] < max(
            candle["open"], candle["close"], candle["low"]
        ):
            raise ValueError("Invalid candle high")

        if candle["low"] > min(
            candle["open"], candle["close"], candle["high"]
        ):
            raise ValueError("Invalid candle low")

        if previous is not None:
            if candle["time"] <= previous:
                raise ValueError("Candles must be chronological")

            if candle["time"] - previous < seconds:
                raise ValueError("Duplicate or overlapping candles")

        previous = candle["time"]
        result.append(candle)

    return result


def run_gold_backtest(
    htf_candles,
    poi_candles,
    entry_candles,
    mode="strict",
    settings=None,
):
    cfg = DEFAULT_SETTINGS.copy()

    if settings:
        unknown = set(settings) - set(cfg)
        if unknown:
            raise ValueError(f"Unknown settings: {sorted(unknown)}")
        cfg.update(settings)

    if mode not in ("strict", "balanced"):
        raise ValueError("Mode must be strict or balanced")

    for key, value in cfg.items():
        cfg[key] = float(value)
        if not isfinite(cfg[key]):
            raise ValueError(f"Invalid setting: {key}")

    for key in (
        "initial_balance_usd",
        "lot_size",
        "contract_size_oz_per_lot",
        "take_profit_price",
        "stop_loss_price",
        "max_trades_per_day",
    ):
        if cfg[key] <= 0:
            raise ValueError(f"{key} must be positive")

    if int(cfg["max_trades_per_day"]) != cfg["max_trades_per_day"]:
        raise ValueError("Daily trade limit must be an integer")

    if not 0 <= cfg["fee_rate_per_side"] <= 1:
        raise ValueError("Invalid fee rate")

    if cfg["slippage_price"] < 0:
        raise ValueError("Slippage cannot be negative")

    htf = validate_candles(htf_candles, "1H", 3600)
    poi = validate_candles(poi_candles, "15M", 900)
    entry = validate_candles(entry_candles, "5M", 300)

    if len(htf) < 40 or len(poi) < 25 or len(entry) < 32:
        raise ValueError("Need 40 1H, 25 15M and 32 5M candles")

    balance = cfg["initial_balance_usd"]
    contract = cfg["lot_size"] * cfg["contract_size_oz_per_lot"]
    daily_trades = defaultdict(int)
    trades = []
    position = None

    for i, candle in enumerate(entry):
        close_time = candle["time"] + 300

        if position:
            side = position["side"]
            hit_sl = (
                candle["low"] <= position["sl"]
                if side == "BUY"
                else candle["high"] >= position["sl"]
            )
            hit_tp = (
                candle["high"] >= position["tp"]
                if side == "BUY"
                else candle["low"] <= position["tp"]
            )

            if hit_sl or hit_tp:
                reason = "SL" if hit_sl else "TP"
                exit_price = position["sl"] if hit_sl else position["tp"]
                slip = cfg["slippage_price"]
                exit_price += -slip if side == "BUY" else slip

                direction = 1 if side == "BUY" else -1
                gross = (
                    (exit_price - position["entry"])
                    * direction
                    * contract
                )
                fees = (
                    abs(position["entry"] * contract)
                    + abs(exit_price * contract)
                ) * cfg["fee_rate_per_side"]
                net = gross - fees
                balance += net

                trades.append({
                    "side": side,
                    "entry": position["entry"],
                    "exit": exit_price,
                    "entry_time": position["time"],
                    "exit_time": close_time,
                    "exit_reason": reason,
                    "gross_pnl_usd": round(gross, 4),
                    "fees_usd": round(fees, 4),
                    "net_pnl_usd": round(net, 4),
                    "result": "WIN" if net > 0 else "LOSS",
                })
                position = None

        if position or i >= len(entry) - 1:
            continue

        # Only use fully closed higher-timeframe candles.
        h = [x for x in htf if x["time"] + 3600 <= close_time]
        p = [x for x in poi if x["time"] + 900 <= close_time]
        e = entry[:i + 1]

        if len(h) < 40 or len(p) < 25 or len(e) < 31:
            continue

        signal = detect_ict_signal(h, p, e, mode=mode, symbol="XAUUSD")
        sig = signal.get("signal")

        if sig not in ("BUY_WATCH", "SELL_WATCH"):
            continue

        side = "BUY" if sig == "BUY_WATCH" else "SELL"
        next_candle = entry[i + 1]
        day = next_candle["time"] // 86400

        if daily_trades[day] >= int(cfg["max_trades_per_day"]):
            continue

        slip = cfg["slippage_price"]
        fill = next_candle["open"] + slip if side == "BUY" else next_candle["open"] - slip

        # Approximate worst-case risk, including estimated fees.
        stop_distance = cfg["stop_loss_price"] + 2 * slip
        estimated_risk = stop_distance * contract
        estimated_risk += abs(fill * contract) * cfg["fee_rate_per_side"] * 2

        if estimated_risk >= balance:
            continue

        daily_trades[day] += 1
        position = {
            "side": side,
            "entry": fill,
            "time": next_candle["time"],
            "tp": fill + cfg["take_profit_price"] if side == "BUY" else fill - cfg["take_profit_price"],
            "sl": fill - cfg["stop_loss_price"] if side == "BUY" else fill + cfg["stop_loss_price"],
        }

    wins = sum(t["net_pnl_usd"] > 0 for t in trades)
    losses = len(trades) - wins
    net_pnl = sum(t["net_pnl_usd"] for t in trades)
    profit = sum(t["net_pnl_usd"] for t in trades if t["net_pnl_usd"] > 0)
    loss = abs(sum(t["net_pnl_usd"] for t in trades if t["net_pnl_usd"] < 0))

    return {
        "symbol": "XAUUSD",
        "mode": mode,
        "live_orders_enabled": LIVE_ORDERS_ENABLED,
        "settings": cfg,
        "initial_balance_usd": cfg["initial_balance_usd"],
        "final_balance_usd": round(balance, 4),
        "net_pnl_usd": round(net_pnl, 4),
        "return_percent": round(net_pnl / cfg["initial_balance_usd"] * 100, 2),
        "total_trades": len(trades),
        "winning_trades": wins,
        "losing_trades": losses,
        "win_rate_percent": round(wins / len(trades) * 100, 2) if trades else 0,
        "profit_factor": round(profit / loss, 3) if loss else None,
        "trades": trades,
        "open_position_at_end": position,
        "warning": (
            "Historical simulation only. Contract multiplier of 10 oz/lot "
            "is an assumption and must be verified. Fees are estimates; "
            "funding is not included. Same-candle SL/TP ambiguity uses SL first."
        ),
    }
