"""
GARRY V7 SMC ICT TRADING BOT

Smart Money Concepts (SMC) analysis.

This module provides deterministic detection for:
- IDM
- Fair Value Gap (FVG)
- Bullish/Bearish Order Block

This is an analysis engine only.
It does not place real trades and makes no profit guarantee.

No GARRY V8 dependency is used.
"""

from dataclasses import dataclass
from typing import Literal

from data.models import Candle
from strategy.market_structure import MarketStructureResult


FVGType = Literal["BULLISH", "BEARISH"]
OBType = Literal["BULLISH", "BEARISH"]
IDMType = Literal["BULLISH", "BEARISH"]


@dataclass(frozen=True)
class FVG:
    """Represents a Fair Value Gap."""

    index: int
    gap_type: FVGType
    lower_price: float
    upper_price: float


@dataclass(frozen=True)
class OrderBlock:
    """Represents a simplified Order Block."""

    index: int
    block_type: OBType
    high: float
    low: float


@dataclass(frozen=True)
class IDM:
    """Represents a simplified inducement level."""

    index: int
    idm_type: IDMType
    price: float


@dataclass(frozen=True)
class SMCResult:
    """Complete SMC analysis result."""

    fvg: tuple[FVG, ...]
    order_blocks: tuple[OrderBlock, ...]
    idm: tuple[IDM, ...]


def detect_fvg(candles: list[Candle]) -> list[FVG]:
    """
    Detect three-candle Fair Value Gaps.

    Bullish FVG:
        Current candle low > candle two positions earlier high.

    Bearish FVG:
        Current candle high < candle two positions earlier low.
    """

    if len(candles) < 3:
        return []

    gaps: list[FVG] = []

    for index in range(2, len(candles)):
        first = candles[index - 2]
        current = candles[index]

        if current.low > first.high:
            gaps.append(
                FVG(
                    index=index,
                    gap_type="BULLISH",
                    lower_price=first.high,
                    upper_price=current.low,
                )
            )

        elif current.high < first.low:
            gaps.append(
                FVG(
                    index=index,
                    gap_type="BEARISH",
                    lower_price=current.high,
                    upper_price=first.low,
                )
            )

    return gaps


def detect_order_blocks(candles: list[Candle]) -> list[OrderBlock]:
    """
    Detect simplified Order Blocks.

    Bullish Order Block:
        A bearish candle immediately before a bullish displacement candle.

    Bearish Order Block:
        A bullish candle immediately before a bearish displacement candle.

    Displacement is represented conservatively by a candle whose body
    is larger than or equal to the previous candle body.
    """

    if len(candles) < 2:
        return []

    blocks: list[OrderBlock] = []

    for index in range(1, len(candles)):
        previous = candles[index - 1]
        current = candles[index]

        previous_body = abs(previous.close - previous.open)
        current_body = abs(current.close - current.open)

        if current_body < previous_body:
            continue

        previous_bearish = previous.close < previous.open
        previous_bullish = previous.close > previous.open

        current_bullish = current.close > current.open
        current_bearish = current.close < current.open

        if previous_bearish and current_bullish:
            blocks.append(
                OrderBlock(
                    index=index - 1,
                    block_type="BULLISH",
                    high=previous.high,
                    low=previous.low,
                )
            )

        elif previous_bullish and current_bearish:
            blocks.append(
                OrderBlock(
                    index=index - 1,
                    block_type="BEARISH",
                    high=previous.high,
                    low=previous.low,
                )
            )

    return blocks


def detect_idm(
    candles: list[Candle],
    market_structure: MarketStructureResult,
) -> list[IDM]:
    """
    Detect simplified inducement levels.

    IDM is represented using the most recent confirmed structural
    swing that sits opposite to the latest structural direction.

    This is intentionally conservative and deterministic.
    """

    if not candles:
        return []

    idm_levels: list[IDM] = []

    latest_break = (
        market_structure.break_events[-1]
        if market_structure.break_events
        else None
    )

    if latest_break is None:
        return idm_levels

    if latest_break.direction == "BULLISH":
        candidate_lows = [
            swing
            for swing in market_structure.swing_lows
            if swing.index < latest_break.index
        ]

        if candidate_lows:
            candidate = candidate_lows[-1]

            idm_levels.append(
                IDM(
                    index=candidate.index,
                    idm_type="BULLISH",
                    price=candidate.price,
                )
            )

    elif latest_break.direction == "BEARISH":
        candidate_highs = [
            swing
            for swing in market_structure.swing_highs
            if swing.index < latest_break.index
        ]

        if candidate_highs:
            candidate = candidate_highs[-1]

            idm_levels.append(
                IDM(
                    index=candidate.index,
                    idm_type="BEARISH",
                    price=candidate.price,
                )
            )

    return idm_levels


def analyze_smc(
    candles: list[Candle],
    market_structure: MarketStructureResult,
) -> SMCResult:
    """
    Run the complete SMC analysis pipeline.
    """

    if not candles:
        return SMCResult(
            fvg=(),
            order_blocks=(),
            idm=(),
        )

    fvg = detect_fvg(candles)
    order_blocks = detect_order_blocks(candles)
    idm = detect_idm(candles, market_structure)

    return SMCResult(
        fvg=tuple(fvg),
        order_blocks=tuple(order_blocks),
        idm=tuple(idm),
    )
