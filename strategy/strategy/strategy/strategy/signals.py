"""
GARRY V7 SMC ICT TRADING BOT

Signal analysis layer.

This module converts market-structure, SMC, and ICT analysis
into a deterministic analysis result.

Important:
- Analysis only.
- Real trading is disabled.
- No broker/API dependency.
- No guaranteed accuracy or profit claim.
- BUY is only an analysis result, not an order instruction.

This module is completely independent of GARRY V8.
"""

from dataclasses import dataclass
from typing import Literal

from data.models import Candle
from strategy.ict import ICTAnalysis
from strategy.market_structure import MarketStructureResult
from strategy.smc import SMCResult


SignalType = Literal["BUY", "NO TRADE"]


@dataclass(frozen=True)
class SignalResult:
    """Final deterministic signal-analysis result."""

    signal: SignalType
    reason: str
    entry: float
    reference_stop_loss: float
    reference_take_profit: float
    risk_reward: float


def _latest_price(candles: list[Candle]) -> float:
    """Return the latest candle close price."""

    if not candles:
        return 0.0

    return candles[-1].close


def _find_reference_stop(
    candles: list[Candle],
    market_structure: MarketStructureResult,
) -> float:
    """
    Find a conservative reference stop level for BUY analysis.

    Priority:
    1. Latest confirmed swing low.
    2. Latest candle low.

    This is a reference level only and does not place an order.
    """

    if market_structure.swing_lows:
        return market_structure.swing_lows[-1].price

    if candles:
        return candles[-1].low

    return 0.0


def _calculate_reference_tp(
    entry: float,
    stop_loss: float,
) -> float:
    """
    Calculate a reference TP using a fixed 2:1 risk/reward ratio.

    This is an analytical reference, not a trading instruction.
    """

    risk = entry - stop_loss

    if risk <= 0:
        return entry

    return entry + (risk * 2.0)


def generate_buy_analysis(
    candles: list[Candle],
    market_structure: MarketStructureResult,
    smc: SMCResult,
    ict: ICTAnalysis,
) -> SignalResult:
    """
    Generate a BUY or NO TRADE analysis.

    BUY requires:
    - Valid bullish ICT setup.
    - Bullish market structure.
    - At least two bullish SMC confirmations.

    Otherwise NO TRADE is returned.
    """

    if not candles:
        return SignalResult(
            signal="NO TRADE",
            reason="No market data available.",
            entry=0.0,
            reference_stop_loss=0.0,
            reference_take_profit=0.0,
            risk_reward=0.0,
        )

    entry = _latest_price(candles)

    bullish_fvg = any(
        gap.gap_type == "BULLISH"
        for gap in smc.fvg
    )

    bullish_ob = any(
        block.block_type == "BULLISH"
        for block in smc.order_blocks
    )

    bullish_idm = any(
        level.idm_type == "BULLISH"
        for level in smc.idm
    )

    bullish_confirmations = sum(
        (
            bullish_fvg,
            bullish_ob,
            bullish_idm,
        )
    )

    if (
        market_structure.trend != "BULLISH"
        or ict.bias != "BULLISH"
        or ict.setup_quality != "VALID"
        or bullish_confirmations < 2
    ):
        return SignalResult(
            signal="NO TRADE",
            reason=(
                "BUY conditions are not fully confirmed. "
                "Wait for stronger bullish structure and SMC/ICT confirmation."
            ),
            entry=entry,
            reference_stop_loss=0.0,
            reference_take_profit=0.0,
            risk_reward=0.0,
        )

    stop_loss = _find_reference_stop(
        candles,
        market_structure,
    )

    if stop_loss >= entry or stop_loss <= 0:
        return SignalResult(
            signal="NO TRADE",
            reason=(
                "Bullish conditions exist, but a valid reference "
                "stop-loss level is not available."
            ),
            entry=entry,
            reference_stop_loss=0.0,
            reference_take_profit=0.0,
            risk_reward=0.0,
        )

    take_profit = _calculate_reference_tp(
        entry,
        stop_loss,
    )

    risk = entry - stop_loss

    risk_reward = (
        (take_profit - entry) / risk
        if risk > 0
        else 0.0
    )

    return SignalResult(
        signal="BUY",
        reason=(
            "Bullish market structure with valid ICT context "
            "and multiple bullish SMC confirmations."
        ),
        entry=entry,
        reference_stop_loss=stop_loss,
        reference_take_profit=take_profit,
        risk_reward=risk_reward,
    )
