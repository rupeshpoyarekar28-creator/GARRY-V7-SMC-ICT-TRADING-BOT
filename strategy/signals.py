"""
GARRY V7 SMC ICT TRADING BOT

Deterministic BUY / SELL / NO TRADE analysis.
Analysis only. Does not place exchange orders.
"""

from dataclasses import dataclass
from typing import Literal

from data.models import Candle
from strategy.ict import ICTAnalysis
from strategy.market_structure import MarketStructureResult
from strategy.smc import SMCResult


SignalType = Literal["BUY", "SELL", "NO TRADE"]


@dataclass(frozen=True)
class SignalResult:
    """Final signal-analysis result."""

    signal: SignalType
    reason: str
    entry: float
    reference_stop_loss: float
    reference_take_profit: float
    risk_reward: float


def _latest_price(candles: list[Candle]) -> float:
    if not candles:
        return 0.0
    return candles[-1].close


def _find_reference_stop(
    candles: list[Candle],
    market_structure: MarketStructureResult,
    side: Literal["BUY", "SELL"],
) -> float:
    """Find a reference SL from the latest swing or candle."""

    if side == "BUY":
        if market_structure.swing_lows:
            return market_structure.swing_lows[-1].price
        return candles[-1].low if candles else 0.0

    if market_structure.swing_highs:
        return market_structure.swing_highs[-1].price
    return candles[-1].high if candles else 0.0


def _no_trade(
    reason: str,
    entry: float = 0.0,
) -> SignalResult:
    return SignalResult(
        signal="NO TRADE",
        reason=reason,
        entry=entry,
        reference_stop_loss=0.0,
        reference_take_profit=0.0,
        risk_reward=0.0,
    )


def _directional_analysis(
    side: Literal["BUY", "SELL"],
    candles: list[Candle],
    market_structure: MarketStructureResult,
    smc: SMCResult,
    ict: ICTAnalysis,
) -> SignalResult:
    if not candles:
        return _no_trade("No market data available.")

    entry = _latest_price(candles)

    if entry <= 0:
        return _no_trade("Invalid latest candle close price.", entry)

    if side == "BUY":
        expected_trend = "BULLISH"
        directional_fvg = "BULLISH"
        directional_ob = "BULLISH"
        directional_idm = "BULLISH"
    else:
        expected_trend = "BEARISH"
        directional_fvg = "BEARISH"
        directional_ob = "BEARISH"
        directional_idm = "BEARISH"

    confirmations = sum((
        any(g.gap_type == directional_fvg for g in smc.fvg),
        any(b.block_type == directional_ob for b in smc.order_blocks),
        any(i.idm_type == directional_idm for i in smc.idm),
    ))

    if (
        market_structure.trend != expected_trend
        or ict.bias != expected_trend
        or ict.setup_quality != "VALID"
        or confirmations < 2
    ):
        return _no_trade(
            f"{side} conditions not fully confirmed. Wait for "
            "matching market structure, ICT bias and at least "
            "two directional SMC confirmations.",
            entry,
        )

    stop_loss = _find_reference_stop(
        candles,
        market_structure,
        side,
    )

    if side == "BUY":
        risk = entry - stop_loss
    else:
        risk = stop_loss - entry

    if stop_loss <= 0 or risk <= 0:
        return _no_trade(
            f"{side} setup has no valid reference stop-loss.",
            entry,
        )

    # Analytical reference target at 2:1 risk/reward.
    if side == "BUY":
        take_profit = entry + (2.0 * risk)
    else:
        take_profit = entry - (2.0 * risk)

    if take_profit <= 0:
        return _no_trade(
            "Calculated reference target is invalid.",
            entry,
        )

    return SignalResult(
        signal=side,
        reason=(
            f"{side} confirmed by matching market structure, "
            "valid ICT context and at least two directional "
            "SMC confirmations."
        ),
        entry=entry,
        reference_stop_loss=stop_loss,
        reference_take_profit=take_profit,
        risk_reward=2.0,
    )


def generate_signal(
    candles: list[Candle],
    market_structure: MarketStructureResult,
    smc: SMCResult,
    ict: ICTAnalysis,
) -> SignalResult:
    """Choose BUY or SELL from confirmed ICT direction."""

    if ict.bias == "BULLISH":
        return _directional_analysis(
            "BUY", candles, market_structure, smc, ict
        )

    if ict.bias == "BEARISH":
        return _directional_analysis(
            "SELL", candles, market_structure, smc, ict
        )

    return _no_trade(
        "ICT bias is neutral. No trade."
    , _latest_price(candles))


def generate_buy_analysis(
    candles: list[Candle],
    market_structure: MarketStructureResult,
    smc: SMCResult,
    ict: ICTAnalysis,
) -> SignalResult:
    """Backward-compatible BUY-only analysis function."""

    return _directional_analysis(
        "BUY", candles, market_structure, smc, ict
    )
