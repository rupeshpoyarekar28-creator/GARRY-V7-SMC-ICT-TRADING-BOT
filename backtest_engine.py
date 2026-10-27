from __future__ import annotations
from dataclasses import dataclass, asdict
from math import isfinite
from typing import Any
from ict_strategy import detect_ict_signal

LIVE_ORDERS_ENABLED = False
TIMEFRAME_SECONDS = {"1h": 3600, "15m": 900, "5m": 300}
DEFAULT_SETTINGS = {
    "initial_balance": 1000.0, "position_size": 1.0,
    "take_profit_points": 20.0, "stop_loss_points": 15.0,
    "fee_rate": 0.0005, "slippage_points": 0.0, "point_value": 1.0,
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
    try: result = float(value)
    except (TypeError, ValueError): raise ValueError(f"{name} must be numeric") from None
    if not isfinite(result): raise ValueError(f"{name} must be finite")
    return result

def _validate(candles: list[dict], name: str, duration: int) -> list[dict]:
    if not isinstance(candles, list): raise ValueError(f"{name} must be a list")
    result, previous = [], None
    for i, c in enumerate(candles):
        if not isinstance(c, dict): raise ValueError(f"{name}[{i}] must be a dictionary")
        if "time" not in c: raise ValueError(f"{name}[{i}] missing time")
        raw_t = _number(c["time"], "time"); t = int(raw_t)
        if t != raw_t or not 1_000_000_000 <= t <= 9_999_999_999:
            raise ValueError(f"{name}[{i}] time must be Unix seconds")
        row = {"time": t, **{k: _number(c[k], k) for k in ("open","high","low","close")}}
        if row["high"] < max(row["open"], row["close"], row["low"]): raise ValueError(f"Invalid high in {name}[{i}]")
        if row["low"] > min(row["open"], row["close"], row["high"]): raise ValueError(f"Invalid low in {name}[{i}]")
        if previous is not None:
            if t <= previous: raise ValueError(f"{name} timestamps must increase")
            if t - previous < duration: raise ValueError(f"{name} has duplicate/overlapping timestamps")
        previous = t; result.append(row)
    return result

def _closed_before(candles: list[dict], timeframe: str, signal_time: int) -> list[dict]:
    duration = TIMEFRAME_SECONDS[timeframe]
    return [c for c in candles if c["time"] + duration <= signal_time]

def _max_drawdown(curve: list[float]) -> float:
    peak, maximum = curve[0], 0.0
    for x in curve:
        peak = max(peak, x); maximum = max(maximum, peak - x)
    return maximum

def run_backtest(htf_candles: list[dict], poi_candles: list[dict], entry_candles: list[dict],
                 symbol: str = "BTCUSD", mode: str = "strict", settings: dict | None = None) -> dict:
    if mode not in ("strict", "balanced"): raise ValueError("mode must be strict or balanced")
    cfg = DEFAULT_SETTINGS.copy()
    if settings:
        unknown = set(settings) - set(cfg)
        if unknown: raise ValueError(f"Unknown settings: {sorted(unknown)}")
        cfg.update(settings)
    for k in cfg: cfg[k] = _number(cfg[k], k)
    if cfg["initial_balance"] <= 0 or cfg["position_size"] <= 0 or cfg["point_value"] <= 0: raise ValueError("Balance, size and point value must be positive")
    if cfg["take_profit_points"] <= 0 or cfg["stop_loss_points"] <= 0: raise ValueError("TP and SL must be positive")
    if cfg["fee_rate"] < 0 or cfg["slippage_points"] < 0: raise ValueError("Fees/slippage cannot be negative")
    htf = _validate(htf_candles, "htf_candles", 3600)
    poi = _validate(poi_candles, "poi_candles", 900)
    entry = _validate(entry_candles, "entry_candles", 300)
    if len(htf) < 40 or len(poi) < 25 or len(entry) < 32: raise ValueError("Need 40 1H, 25 15M and 32 5M candles")

    balance = cfg["initial_balance"]; equity = [balance]; trades = []; position = None
    diag = {"candles_checked":0,"wait_signals":0,"buy_signals":0,"sell_signals":0,
            "reasons":{},"failed_conditions":{},"samples":[]}

    for i in range(len(entry)-1):
        c = entry[i]; close_time = c["time"] + 300
        if position is not None:
            side, sl, tp = position["side"], position["sl"], position["tp"]
            hit_sl = c["low"] <= sl if side == "BUY" else c["high"] >= sl
            hit_tp = c["high"] >= tp if side == "BUY" else c["low"] <= tp
            if hit_sl or hit_tp:
                reason = "SL" if hit_sl else "TP"  # conservative if both touched
                raw_exit = sl if hit_sl else tp
                slip = cfg["slippage_points"]
                exit_price = raw_exit - slip if side == "BUY" else raw_exit + slip
                direction = 1 if side == "BUY" else -1
                size, mult = cfg["position_size"], cfg["point_value"]
                gross = (exit_price-position["entry"]) * direction * size * mult
                fees = (abs(position["entry"])+abs(exit_price))*size*mult*cfg["fee_rate"]
                slip_cost = (position["entry_slippage"]+slip)*size*mult
                net = gross-fees
                balance += net
                trades.append(Trade(side,position["entry"],exit_price,size,gross,fees,slip_cost,net,
                                    "WIN" if net > 0 else "LOSS",position["entry_time"],close_time,reason))
                equity.append(balance); position = None
        if position is not None: continue

        h = _closed_before(htf,"1h",close_time); p = _closed_before(poi,"15m",close_time); e = entry[:i+1]
        if len(h)<40 or len(p)<25 or len(e)<31: continue
        diag["candles_checked"] += 1
        signal = detect_ict_signal(
            [{**{k:x[k] for k in ("open","high","low","close")},"time":x["time"]} for x in h],
            [{**{k:x[k] for k in ("open","high","low","close")},"time":x["time"]} for x in p],
            [{**{k:x[k] for k in ("open","high","low","close")},"time":x["time"]} for x in e],
            mode=mode,symbol=symbol)
        st, reason = signal.get("signal","WAIT"), signal.get("reason","No reason")
        if st == "WAIT":
            diag["wait_signals"] += 1; diag["reasons"][reason] = diag["reasons"].get(reason,0)+1
            for key in ("failed_buy_conditions","failed_sell_conditions"):
                for condition in signal.get(key,[]):
                    diag["failed_conditions"][condition] = diag["failed_conditions"].get(condition,0)+1
            if len(diag["samples"])<12:
                diag["samples"].append({"time":close_time,"reason":reason,"bias_1h":signal.get("bias_1h"),
                    "sweep_15m":signal.get("sweep_15m"),"structure_5m":signal.get("structure_5m"),
                    "fvg_5m":signal.get("fvg_5m"),"displacement":signal.get("displacement"),
                    "failed_buy_conditions":signal.get("failed_buy_conditions",[]),
                    "failed_sell_conditions":signal.get("failed_sell_conditions",[])})
        if st not in ("BUY_WATCH","SELL_WATCH"): continue
        side = "BUY" if st=="BUY_WATCH" else "SELL"
        diag["buy_signals" if side=="BUY" else "sell_signals"] += 1
        slip = cfg["slippage_points"]
        fill = entry[i+1]["open"] + slip if side=="BUY" else entry[i+1]["open"] - slip
        position = {"side":side,"entry":fill,"tp":fill+cfg["take_profit_points"] if side=="BUY" else fill-cfg["take_profit_points"],
                    "sl":fill-cfg["stop_loss_points"] if side=="BUY" else fill+cfg["stop_loss_points"],
                    "entry_time":entry[i+1]["time"],"entry_slippage":slip}

    open_position = None
    if position is not None:
        last = entry[-1]; direction = 1 if position["side"]=="BUY" else -1
        size, mult, slip = cfg["position_size"], cfg["point_value"], cfg["slippage_points"]
        gross_unreal = (last["close"]-position["entry"])*direction*size*mult
        est_exit = last["close"]-slip if position["side"]=="BUY" else last["close"]+slip
        est_fees = (abs(position["entry"])+abs(est_exit))*size*mult*cfg["fee_rate"]
        open_position = {**position,"last_close":last["close"],"unrealized_gross_pnl":gross_unreal,
                         "estimated_exit_fees":est_fees,
                         "estimated_unrealized_net_pnl":gross_unreal-slip*size*mult-est_fees}

    wins = sum(t.net_pnl>0 for t in trades); losses = len(trades)-wins
    pnl = sum(t.net_pnl for t in trades); fees = sum(t.fees for t in trades)
    gp = sum(t.net_pnl for t in trades if t.net_pnl>0)
    gl = abs(sum(t.net_pnl for t in trades if t.net_pnl<0))
    pf = gp/gl if gl else (None if gp else 0.0)
    return {"symbol":symbol,"mode":mode,"timeframes":{"direction":"1h","poi":"15m","entry":"5m"},
        "live_orders_enabled":False,"initial_balance":cfg["initial_balance"],
        "final_balance_closed_trades_only":balance,"net_pnl_closed_trades_only":pnl,
        "return_percent_closed_trades_only":pnl/cfg["initial_balance"]*100,
        "total_trades":len(trades),"winning_trades":wins,"losing_trades":losses,
        "win_rate_percent":wins/len(trades)*100 if trades else 0.0,"profit_factor":pf,
        "max_drawdown_closed_trades_only":_max_drawdown(equity),"total_fees":fees,
        "estimated_slippage_cost":sum(t.slippage_cost for t in trades),
        "open_position_at_end":open_position,"trades":[asdict(t) for t in trades],
        "diagnostics":diag,
        "warning":"Prototype only. Fees/slippage are estimates; verify exchange contract multiplier, funding, tick/quantity rules and candle quality. Drawdown is closed-trade-only and excludes intratrade movement. Open P&L is reported separately. No exchange orders are placed."}
