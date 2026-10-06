"""
GARRY V7 SMC ICT TRADING BOT

Market Structure Engine.

Responsibilities:
- Detect swing highs and swing lows.
- Classify structure as HH, HL, LH, or LL.
- Detect BOS (Break of Structure).
- Detect CHOCH (Change of Character).

The logic is deterministic and testable.

This module is completely independent of GARRY V8.
"""

from dataclasses import dataclass
from typing import Literal

from data.models import Candle


StructureType = Literal["HH", "HL", "LH", "LL"]
BreakType = Literal["BOS", "CHOCH", "NONE"]
TrendType = Literal["BULLISH", "BEARISH", "RANGE", "UNKNOWN"]


@dataclass(frozen=True)
class SwingPoint:
    """Represents a detected swing high or swing low."""

    index: int
    price: float
    point_type: Literal["HIGH", "LOW"]


@dataclass(frozen=True)
class StructureEvent:
    """Represents one market-structure event."""

    index: int
    structure_type: StructureType
    price: float


@dataclass(frozen=True)
class BreakEvent:
    """Represents a BOS or CHOCH event."""

    index: int
    break_type: BreakType
    direction: Literal["BULLISH", "BEARISH"]
    level: float


@dataclass(frozen=True)
class MarketStructureResult:
    """Complete market-structure analysis result."""

    trend: TrendType
    swing_highs: tuple[SwingPoint, ...]
    swing_lows: tuple[SwingPoint, ...]
    structure_events: tuple[StructureEvent, ...]
    break_events: tuple[BreakEvent, ...]


def find_swing_highs(
    candles: list[Candle],
    left: int = 1,
    right: int = 1,
) -> list[SwingPoint]:
    """Find local swing highs."""

    if left < 1 or right < 1:
        raise ValueError("left and right must be greater than zero")

    if len(candles) < left + right + 1:
        return []

    swings: list[SwingPoint] = []

    for index in range(left, len(candles) - right):
        current_high = candles[index].high

        left_highs = [
            candles[position].high
            for position in range(index - left, index)
        ]

        right_highs = [
            candles[position].high
            for position in range(index + 1, index + right + 1)
        ]

        if (
            current_high >= max(left_highs)
            and current_high >= max(right_highs)
        ):
            swings.append(
                SwingPoint(
                    index=index,
                    price=current_high,
                    point_type="HIGH",
                )
            )

    return swings


def find_swing_lows(
    candles: list[Candle],
    left: int = 1,
    right: int = 1,
) -> list[SwingPoint]:
    """Find local swing lows."""

    if left < 1 or right < 1:
        raise ValueError("left and right must be greater than zero")

    if len(candles) < left + right + 1:
        return []

    swings: list[SwingPoint] = []

    for index in range(left, len(candles) - right):
        current_low = candles[index].low

        left_lows = [
            candles[position].low
            for position in range(index - left, index)
        ]

        right_lows = [
            candles[position].low
            for position in range(index + 1, index + right + 1)
        ]

        if (
            current_low <= min(left_lows)
            and current_low <= min(right_lows)
        ):
            swings.append(
                SwingPoint(
                    index=index,
                    price=current_low,
                    point_type="LOW",
                )
            )

    return swings


def classify_structure(
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
) -> list[StructureEvent]:
    """Classify swing points as HH, HL, LH, or LL."""

    events: list[StructureEvent] = []

    previous_high: SwingPoint | None = None
    previous_low: SwingPoint | None = None

    all_swings = sorted(
        [*swing_highs, *swing_lows],
        key=lambda swing: swing.index,
    )

    for swing in all_swings:
        if swing.point_type == "HIGH":
            if previous_high is not None:
                structure_type: StructureType = (
                    "HH"
                    if swing.price > previous_high.price
                    else "LH"
                )

                events.append(
                    StructureEvent(
                        index=swing.index,
                        structure_type=structure_type,
                        price=swing.price,
                    )
                )

            previous_high = swing

        else:
            if previous_low is not None:
                structure_type: StructureType = (
                    "HL"
                    if swing.price > previous_low.price
                    else "LL"
                )

                events.append(
                    StructureEvent(
                        index=swing.index,
                        structure_type=structure_type,
                        price=swing.price,
                    )
                )

            previous_low = swing

    return events


def detect_breaks(
    candles: list[Candle],
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
) -> list[BreakEvent]:
    """
    Detect bullish and bearish structural breaks.

    A bullish break occurs when a candle closes above a previous
    swing high.

    A bearish break occurs when a candle closes below a previous
    swing low.

    A break against the established trend is classified as CHOCH.
    """

    breaks: list[BreakEvent] = []

    established_trend: TrendType = "UNKNOWN"

    broken_highs: set[int] = set()
    broken_lows: set[int] = set()

    high_levels = sorted(
        swing_highs,
        key=lambda swing: swing.index,
    )

    low_levels = sorted(
        swing_lows,
        key=lambda swing: swing.index,
    )

    for index, candle in enumerate(candles):

        available_highs = [
            swing
            for swing in high_levels
            if swing.index < index
        ]

        available_lows = [
            swing
            for swing in low_levels
            if swing.index < index
        ]

        if available_highs:
            latest_high = available_highs[-1]

            if (
                candle.close > latest_high.price
                and latest_high.index not in broken_highs
            ):
                break_type: BreakType = (
                    "CHOCH"
                    if established_trend == "BEARISH"
                    else "BOS"
                )

                breaks.append(
                    BreakEvent(
                        index=index,
                        break_type=break_type,
                        direction="BULLISH",
                        level=latest_high.price,
                    )
                )

                established_trend = "BULLISH"
                broken_highs.add(latest_high.index)

        if available_lows:
            latest_low = available_lows[-1]

            if (
                candle.close < latest_low.price
                and latest_low.index not in broken_lows
            ):
                break_type = (
                    "CHOCH"
                    if established_trend == "BULLISH"
                    else "BOS"
                )

                breaks.append(
                    BreakEvent(
                        index=index,
                        break_type=break_type,
                        direction="BEARISH",
                        level=latest_low.price,
                    )
                )

                established_trend = "BEARISH"
                broken_lows.add(latest_low.index)

    return breaks


def determine_trend(
    structure_events: list[StructureEvent],
    break_events: list[BreakEvent],
) -> TrendType:
    """Determine the broad market-structure direction."""

    if break_events:
        return break_events[-1].direction

    recent_events = structure_events[-4:]

    if not recent_events:
        return "UNKNOWN"

    bullish_count = sum(
        event.structure_type in {"HH", "HL"}
        for event in recent_events
    )

    bearish_count = sum(
        event.structure_type in {"LH", "LL"}
        for event in recent_events
    )

    if bullish_count > bearish_count:
        return "BULLISH"

    if bearish_count > bullish_count:
        return "BEARISH"

    return "RANGE"


def analyze_market_structure(
    candles: list[Candle],
    left: int = 1,
    right: int = 1,
) -> MarketStructureResult:
    """Run the complete market-structure analysis pipeline."""

    if not candles:
        return MarketStructureResult(
            trend="UNKNOWN",
            swing_highs=(),
            swing_lows=(),
            structure_events=(),
            break_events=(),
        )

    swing_highs = find_swing_highs(
        candles,
        left=left,
        right=right,
    )

    swing_lows = find_swing_lows(
        candles,
        left=left,
        right=right,
    )

    structure_events = classify_structure(
        swing_highs,
        swing_lows,
    )

    break_events = detect_breaks(
        candles,
        swing_highs,
        swing_lows,
    )

    trend = determine_trend(
        structure_events,
        break_events,
    )

    return MarketStructureResult(
        trend=trend,
        swing_highs=tuple(swing_highs),
        swing_lows=tuple(swing_lows),
        structure_events=tuple(structure_events),
        break_events=tuple(break_events),
    )
