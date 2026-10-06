"""
GARRY V7 SMC ICT TRADING BOT

ICT analysis layer.

This module combines market structure and SMC information
to produce a deterministic ICT-style directional assessment.

This is analysis only.
No real order execution is performed.
No profit or accuracy guarantee is made.

This module is completely independent of GARRY V8.
"""

from dataclasses import dataclass
from typing import Literal

from data.models import Candle
from strategy.market_structure import MarketStructureResult
from strategy.smc import SMCResult


ICTBias = Literal["BULLISH", "BEARISH", "NEUTRAL"]
SetupQuality = Literal["VALID", "WATCH", "NO_SETUP"]


@dataclass(frozen=True)
class ICTAnalysis:
    """Result of the ICT directional analysis."""

    bias: ICTBias
    setup_quality: SetupQuality
    structure_confirmed: bool
    liquidity_context: str
    reason: str


def analyze_ict(
    candles: list[Candle],
    market_structure: MarketStructureResult,
    smc: SMCResult,
) -> ICTAnalysis:
    """
    Produce a deterministic ICT-style analysis.

    BUY-side context requires:
    - Bullish market structure.
    - Bullish SMC evidence such as FVG, bullish OB, or bullish IDM.

    BEARISH context is evaluated similarly.

    A signal is not generated here. Final trade setup decisions
    are handled by the signals module.
    """

    if not candles:
        return ICTAnalysis(
            bias="NEUTRAL",
            setup_quality="NO_SETUP",
            structure_confirmed=False,
            liquidity_context="NO_DATA",
            reason="No market data available.",
        )

    bullish_fvg = any(
        gap.gap_type == "BULLISH"
        for gap in smc.fvg
    )

    bearish_fvg = any(
        gap.gap_type == "BEARISH"
        for gap in smc.fvg
    )

    bullish_ob = any(
        block.block_type == "BULLISH"
        for block in smc.order_blocks
    )

    bearish_ob = any(
        block.block_type == "BEARISH"
        for block in smc.order_blocks
    )

    bullish_idm = any(
        level.idm_type == "BULLISH"
        for level in smc.idm
    )

    bearish_idm = any(
        level.idm_type == "BEARISH"
        for level in smc.idm
    )

    bullish_evidence = sum(
        (
            bullish_fvg,
            bullish_ob,
            bullish_idm,
        )
    )

    bearish_evidence = sum(
        (
            bearish_fvg,
            bearish_ob,
            bearish_idm,
        )
    )

    if market_structure.trend == "BULLISH":
        if bullish_evidence >= 2:
            return ICTAnalysis(
                bias="BULLISH",
                setup_quality="VALID",
                structure_confirmed=True,
                liquidity_context="BULLISH_STRUCTURE",
                reason=(
                    "Bullish market structure confirmed with "
                    "multiple bullish SMC conditions."
                ),
            )

        if bullish_evidence == 1:
            return ICTAnalysis(
                bias="BULLISH",
                setup_quality="WATCH",
                structure_confirmed=True,
                liquidity_context="BULLISH_STRUCTURE",
                reason=(
                    "Bullish structure exists, but SMC confirmation "
                    "is incomplete."
                ),
            )

        return ICTAnalysis(
            bias="BULLISH",
            setup_quality="WATCH",
            structure_confirmed=True,
            liquidity_context="BULLISH_STRUCTURE",
            reason="Bullish structure without sufficient SMC confirmation.",
        )

    if market_structure.trend == "BEARISH":
        if bearish_evidence >= 2:
            return ICTAnalysis(
                bias="BEARISH",
                setup_quality="VALID",
                structure_confirmed=True,
                liquidity_context="BEARISH_STRUCTURE",
                reason=(
                    "Bearish market structure confirmed with "
                    "multiple bearish SMC conditions."
                ),
            )

        if bearish_evidence == 1:
            return ICTAnalysis(
                bias="BEARISH",
                setup_quality="WATCH",
                structure_confirmed=True,
                liquidity_context="BEARISH_STRUCTURE",
                reason=(
                    "Bearish structure exists, but SMC confirmation "
                    "is incomplete."
                ),
            )

        return ICTAnalysis(
            bias="BEARISH",
            setup_quality="WATCH",
            structure_confirmed=True,
            liquidity_context="BEARISH_STRUCTURE",
            reason="Bearish structure without sufficient SMC confirmation.",
        )

    return ICTAnalysis(
        bias="NEUTRAL",
        setup_quality="NO_SETUP",
        structure_confirmed=False,
        liquidity_context="RANGE_OR_UNKNOWN",
        reason=(
            "Market structure is not sufficiently directional "
            "for an ICT setup."
        ),
    )
