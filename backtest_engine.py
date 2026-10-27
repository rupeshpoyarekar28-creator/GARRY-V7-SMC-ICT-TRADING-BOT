from __future__ import annotations

from dataclasses import dataclass, asdict
from math import isfinite
from typing import Any

from ict_strategy import detect_ict_signal

LIVE_ORDERS_ENABLED = False
TIMEFRAME_SECONDS = {"1h": 3600, "15m": 900, "5m": 300}

# Delta Exchange India BTCUSD model. Verify these values against the live
# contract/fee page before relying on results; this code places no orders.
DEFAULT_SETTINGS = {
    "initial_balance": 1000.0,       # INR
    "position_size": 1.0,             # lots/contracts, not BTC
    "lot_size_btc": 0.001,            # BTC per lot
    "usd_inr_rate": 85.0,             # platform reference conversion; configurable
    "take_profit_points": 20.0,       # USD/BTC price movement
    "stop_loss_points": 15.0,         # USD/BTC price movement
    "fee_rate": 0.0005,               # 0.05% per side, taker assumption
    "fee_gst_rate": 0.18,              # GST on trading fees
    "slippage_points": 0.0,             # USD/BTC per side; scenario assumption
    "funding_cost_inr_per_lot": 0.0,   # placeholder; historical funding not provided
    "max_risk_per_trade_pct": 1.0,      # reject entries if estimated SL loss exceeds this
}

@dataclass
class Trade:
    side: str
    entry: float
    exit: float
    size_lots: float
    gross_pnl_inr: float
    entry_fee_inr: float
    exit_fee_inr: float
    gst_inr: float
    funding_inr: float
    slippage_cost_inr: float
    total_costs_inr: float
    net_pnl_inr: float
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

def _validate(candles: list[dict], name: str, duration: int) -> list[dict]:
    if not isinstance(candles, list):
        raise ValueError(f"{name} must be a list")
    result, previous = [], None
    for i, c in enumerate(candles):
        if not isinstance(c, dict):
            raise ValueError(f"{name}[{i}] must be a dictionary")
        if "time" not in c:
            raise ValueError(f"{name}[{i}] missing time")
        raw_t = _number(c["time"], f"{name}[{i}].time")
        t = int(raw_t)
        if t != raw_t or not 1_000_000_000 <= t <= 9_999_999_999:
            raise ValueError(f"{name}[{i}] time must be Unix seconds")
        row = {"time": t, **{k: _number(c[k], f"{name}[{i}].{k}")
                              for k in ("open", "high", "low", "close")}}
        if row["high"] < max(row["open"], row["close"], row["low"]):
            raise ValueError(f"Invalid high in {name}[{i}]")
        if row["low"] > min(row["open"], row["close"], row["high"]):
            raise ValueError(f"Invalid low in {name}[{i}]")
        if previous is not None:
            if t <= previous:
                raise ValueError(f"{name} timestamps must increase")
            if t - previous < duration:
                raise ValueError(f"{name} has duplicate/overlapping timestamps")
        previous = t
        result.append(row)
    return result

def _closed_before(candles: list[dict], timeframe: str, signal_time: int) -> list[dict]:
    duration = TIMEFRAME_SECONDS[timeframe]
    return [c for c in candles if c["time"] + duration <= signal_time]

def _max_drawdown(curve: list[float]) -> float:
    if not curve:
        return 0.0
    peak, maximum = curve[0], 0.0
    for x in curve:
        peak = max(peak, x)
        maximum = max(maximum, peak - x)
    return maximum

def _notional_inr(price: float, lots: float, cfg: dict) -> float:
    return abs(price) * lots * cfg["lot_size_btc"] * cfg["usd_inr_rate"]

def _fee_inr(price: float, lots: float, cfg: dict) -> float:
    return _notional_inr(price, lots, cfg) * cfg["fee_rate"]

def _gross_pnl_inr(entry: float, exit_price: float, side: str, lots: float, cfg: dict) -> float:
    direction = 1.0 if side == "BUY" else -1.0
    return (exit_price - entry) * direction * lots * cfg["lot_size_btc"] * cfg["usd_inr_rate"]

def _estimated_stop_loss_inr(entry: float, side: str, lots: float, cfg: dict) -> float:
    slippage = cfg["slippage_points"]
    exit_price = entry - cfg["stop_loss_points"] if side == "BUY" else entry + cfg["stop_loss_points"]
    exit_price = exit_price - slippage if side == "BUY" else exit_price + slippage
    entry_fill = entry + slippage if side == "BUY" else entry - slippage
    gross = abs(_gross_pnl_inr(entry_fill, exit_price, side, lots, cfg))
    fees = _fee_inr(entry_fill, lots, cfg) + _fee_inr(exit_price, lots, cfg)
    gst = fees * cfg["fee_gst_rate"]
    # gross already includes adverse entry/exit slippage through the adjusted fills;
    # do not add slippage a second time to estimated risk.
    funding = cfg["funding_cost_inr_per_lot"] * lots
    return gross + fees + gst + funding

def run_backtest(
    htf_candles: list[dict],
    poi_candles: list[dict],
    entry_candles: list[dict],
    symbol: str = "BTCUSD",
    mode: str = "strict",
    settings: dict | None = None,
) -> dict:
    if symbol != "BTCUSD":
        raise ValueError("This accounting model is verified only for BTCUSD; other symbols need their own contract specification.")
    if mode not in ("strict", "balanced"):
        raise ValueError("mode must be strict or balanced")

    cfg = DEFAULT_SETTINGS.copy()
    if settings:
        unknown = set(settings) - set(cfg)
        if unknown:
            raise ValueError(f"Unknown settings: {sorted(unknown)}")
        cfg.update(settings)
    for k in cfg:
        cfg[k] = _number(cfg[k], k)
    for k in ("initial_balance", "position_size", "lot_size_btc", "usd_inr_rate"):
        if cfg[k] <= 0:
            raise ValueError(f"{k} must be positive")
    if cfg["take_profit_points"] <= 0 or cfg["stop_loss_points"] <= 0:
        raise ValueError("TP and SL must be positive")
    if not 0 <= cfg["fee_rate"] <= 1 or not 0 <= cfg["fee_gst_rate"] <= 1:
        raise ValueError("fee_rate and fee_gst_rate must be between 0 and 1")
    if cfg["slippage_points"] < 0 or cfg["funding_cost_inr_per_lot"] < 0:
        raise ValueError("slippage and funding placeholder cannot be negative")
    if cfg["max_risk_per_trade_pct"] <= 0:
        raise ValueError("max_risk_per_trade_pct must be positive")

    htf = _validate(htf_candles, "htf_candles", 3600)
    poi = _validate(poi_candles, "poi_candles", 900)
    entry = _validate(entry_candles, "entry_candles", 300)
    if len(htf) < 40 or len(poi) < 25 or len(entry) < 32:
        raise ValueError("Need 40 1H, 25 15M and 32 5M candles")

    balance = cfg["initial_balance"]
    equity_curve = [balance]
    trades: list[Trade] = []
    position = None
    diag = {
        "candles_checked": 0, "wait_signals": 0, "buy_signals": 0, "sell_signals": 0,
        "risk_rejected_signals": 0, "reasons": {}, "failed_conditions": {}, "samples": [],
        "notes": [
            "PnL is estimated in INR using lot_size_btc and usd_inr_rate.",
            "Funding is a user-configured placeholder, not historical funding data.",
            "Same-candle SL/TP ambiguity is resolved conservatively in favor of SL.",
            "Last candle is checked for exit; no entry is opened without a following candle."
        ],
    }
    peak_equity = balance
    max_intratrade_drawdown = 0.0

    for i, c in enumerate(entry):
        close_time = c["time"] + 300

        # Evaluate open position against this candle. The candle follows the
        # entry candle, because positions are entered at the next candle open.
        if position is not None:
            side = position["side"]
            sl, tp = position["sl"], position["tp"]
            hit_sl = c["low"] <= sl if side == "BUY" else c["high"] >= sl
            hit_tp = c["high"] >= tp if side == "BUY" else c["low"] <= tp

            # Approximate adverse excursion using candle low/high; this is a
            # conservative bar-based estimate, not tick-by-tick liquidation logic.
            adverse_price = c["low"] if side == "BUY" else c["high"]
            adverse_gross = _gross_pnl_inr(position["entry"], adverse_price, side, position["size_lots"], cfg)
            mark_equity = balance + min(0.0, adverse_gross)
            peak_equity = max(peak_equity, mark_equity)
            max_intratrade_drawdown = max(max_intratrade_drawdown, peak_equity - mark_equity)

            if hit_sl or hit_tp:
                reason = "SL" if hit_sl else "TP"
                raw_exit = sl if hit_sl else tp
                slip = cfg["slippage_points"]
                exit_price = raw_exit - slip if side == "BUY" else raw_exit + slip
                lots = position["size_lots"]
                gross = _gross_pnl_inr(position["entry"], exit_price, side, lots, cfg)
                entry_fee = _fee_inr(position["entry"], lots, cfg)
                exit_fee = _fee_inr(exit_price, lots, cfg)
                fee_before_gst = entry_fee + exit_fee
                gst = fee_before_gst * cfg["fee_gst_rate"]
                funding = cfg["funding_cost_inr_per_lot"] * lots
                slippage_cost = (position["entry_slippage"] + slip) * lots * cfg["lot_size_btc"] * cfg["usd_inr_rate"]
                total_costs = fee_before_gst + gst + funding
                net = gross - total_costs
                balance += net
                trades.append(Trade(
                    side=side, entry=position["entry"], exit=exit_price, size_lots=lots,
                    gross_pnl_inr=gross, entry_fee_inr=entry_fee, exit_fee_inr=exit_fee,
                    gst_inr=gst, funding_inr=funding, slippage_cost_inr=slippage_cost,
                    total_costs_inr=total_costs, net_pnl_inr=net,
                    result="WIN" if net > 0 else "LOSS",
                    entry_time=position["entry_time"], exit_time=close_time, exit_reason=reason
                ))
                equity_curve.append(balance)
                peak_equity = max(peak_equity, balance)
                position = None

        # Signal is formed only after this candle has closed. If no next candle
        # exists, do not create a position that cannot be simulated.
        if position is not None or i >= len(entry) - 1:
            continue

        h = _closed_before(htf, "1h", close_time)
        p = _closed_before(poi, "15m", close_time)
        e = entry[:i + 1]
        if len(h) < 40 or len(p) < 25 or len(e) < 31:
            continue
        diag["candles_checked"] += 1
        signal = detect_ict_signal(h, p, e, mode=mode, symbol=symbol)
        st = signal.get("signal", "WAIT")
        reason = signal.get("reason", "No reason")
        if st == "WAIT":
            diag["wait_signals"] += 1
            diag["reasons"][reason] = diag["reasons"].get(reason, 0) + 1
            for key in ("failed_buy_conditions", "failed_sell_conditions"):
                for condition in signal.get(key, []):
                    diag["failed_conditions"][condition] = diag["failed_conditions"].get(condition, 0) + 1
            if len(diag["samples"]) < 12:
                diag["samples"].append({
                    "time": close_time, "reason": reason, "bias_1h": signal.get("bias_1h"),
                    "sweep_15m": signal.get("sweep_15m"), "structure_5m": signal.get("structure_5m"),
                    "fvg_5m": signal.get("fvg_5m"), "displacement": signal.get("displacement"),
                    "failed_buy_conditions": signal.get("failed_buy_conditions", []),
                    "failed_sell_conditions": signal.get("failed_sell_conditions", [])
                })
        if st not in ("BUY_WATCH", "SELL_WATCH"):
            continue

        side = "BUY" if st == "BUY_WATCH" else "SELL"
        diag["buy_signals" if side == "BUY" else "sell_signals"] += 1
        next_open = entry[i + 1]["open"]
        slip = cfg["slippage_points"]
        fill = next_open + slip if side == "BUY" else next_open - slip
        estimated_risk = _estimated_stop_loss_inr(next_open, side, cfg["position_size"], cfg)
        risk_limit = balance * cfg["max_risk_per_trade_pct"] / 100.0
        if estimated_risk > risk_limit:
            diag["risk_rejected_signals"] += 1
            diag["reasons"]["Estimated stop loss exceeds risk limit"] = diag["reasons"].get("Estimated stop loss exceeds risk limit", 0) + 1
            continue

        position = {
            "side": side, "entry": fill,
            "tp": fill + cfg["take_profit_points"] if side == "BUY" else fill - cfg["take_profit_points"],
            "sl": fill - cfg["stop_loss_points"] if side == "BUY" else fill + cfg["stop_loss_points"],
            "entry_time": entry[i + 1]["time"], "entry_slippage": slip,
            "size_lots": cfg["position_size"],
        }

    open_position = None
    if position is not None:
        last = entry[-1]
        side = position["side"]
        close = last["close"]
        est_exit = close - cfg["slippage_points"] if side == "BUY" else close + cfg["slippage_points"]
        gross = _gross_pnl_inr(position["entry"], close, side, position["size_lots"], cfg)
        entry_fee = _fee_inr(position["entry"], position["size_lots"], cfg)
        exit_fee = _fee_inr(est_exit, position["size_lots"], cfg)
        gst = (entry_fee + exit_fee) * cfg["fee_gst_rate"]
        funding = cfg["funding_cost_inr_per_lot"] * position["size_lots"]
        slippage_cost = 2 * cfg["slippage_points"] * position["size_lots"] * cfg["lot_size_btc"] * cfg["usd_inr_rate"]
        open_position = {
            **position, "last_close": close, "unrealized_gross_pnl_inr": gross,
            "estimated_entry_fee_inr": entry_fee, "estimated_exit_fee_inr": exit_fee,
            "estimated_gst_inr": gst, "estimated_funding_inr": funding,
            "estimated_slippage_cost_inr": slippage_cost,
            "estimated_unrealized_net_pnl_inr": gross - entry_fee - exit_fee - gst - funding,
        }

    wins = sum(t.net_pnl_inr > 0 for t in trades)
    losses = len(trades) - wins
    pnl = sum(t.net_pnl_inr for t in trades)
    total_fees = sum(t.entry_fee_inr + t.exit_fee_inr for t in trades)
    total_gst = sum(t.gst_inr for t in trades)
    gross_profit = sum(t.net_pnl_inr for t in trades if t.net_pnl_inr > 0)
    gross_loss = abs(sum(t.net_pnl_inr for t in trades if t.net_pnl_inr < 0))
    pf = gross_profit / gross_loss if gross_loss else (None if gross_profit else 0.0)

    return {
        "symbol": symbol, "mode": mode, "currency": "INR",
        "timeframes": {"direction": "1h", "poi": "15m", "entry": "5m"},
        "live_orders_enabled": False, "initial_balance_inr": cfg["initial_balance"],
        "final_balance_closed_trades_only_inr": balance,
        "net_pnl_closed_trades_only_inr": pnl,
        "return_percent_closed_trades_only": pnl / cfg["initial_balance"] * 100,
        "total_trades": len(trades), "winning_trades": wins, "losing_trades": losses,
        "win_rate_percent": wins / len(trades) * 100 if trades else 0.0,
        "profit_factor_net": pf, "max_drawdown_closed_trades_only_inr": _max_drawdown(equity_curve),
        "estimated_max_intratrade_drawdown_inr": max_intratrade_drawdown,
        "total_trading_fees_inr": total_fees, "total_gst_inr": total_gst,
        "estimated_slippage_cost_inr": sum(t.slippage_cost_inr for t in trades),
        "estimated_funding_inr": sum(t.funding_inr for t in trades),
        "settings": cfg, "open_position_at_end": open_position,
        "trades": [asdict(t) for t in trades], "diagnostics": diag,
        "warning": (
            "Historical simulation only; no exchange orders. USD/INR conversion, fees and lot size are configurable assumptions. "
            "Funding is not historical unless explicitly supplied. OHLC bars cannot resolve intrabar price path; SL is assumed first "
            "when both SL and TP are touched. Results do not guarantee future profitability."
        ),
    }
