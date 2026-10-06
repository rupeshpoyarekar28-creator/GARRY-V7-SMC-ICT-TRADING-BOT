"""
GARRY V7 SMC ICT TRADING BOT

Risk Management module.

Responsibilities:
- Calculate trade risk.
- Calculate position size.
- Calculate risk/reward.
- Validate BUY setup levels.

This module does NOT place trades.

No broker/API dependency.
No GARRY V8 dependency.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskResult:
    """Calculated risk information."""

    entry: float
    stop_loss: float
    take_profit: float
    risk_per_unit: float
    reward_per_unit: float
    risk_reward: float
    risk_amount: float
    position_size: float
    valid: bool
    reason: str


def calculate_risk(
    entry: float,
    stop_loss: float,
    take_profit: float,
    account_balance: float,
    risk_percent: float = 1.0,
) -> RiskResult:
    """
    Calculate BUY-side risk information.

    Position size is calculated using:

        risk amount = account balance × risk %

        position size = risk amount / risk per unit

    This is a calculation only.
    It does not submit or execute an order.
    """

    if entry <= 0:
        return RiskResult(
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_per_unit=0.0,
            reward_per_unit=0.0,
            risk_reward=0.0,
            risk_amount=0.0,
            position_size=0.0,
            valid=False,
            reason="Entry price must be greater than zero.",
        )

    if stop_loss <= 0:
        return RiskResult(
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_per_unit=0.0,
            reward_per_unit=0.0,
            risk_reward=0.0,
            risk_amount=0.0,
            position_size=0.0,
            valid=False,
            reason="Stop-loss must be greater than zero.",
        )

    if stop_loss >= entry:
        return RiskResult(
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_per_unit=0.0,
            reward_per_unit=0.0,
            risk_reward=0.0,
            risk_amount=0.0,
            position_size=0.0,
            valid=False,
            reason="For a BUY setup, stop-loss must be below entry.",
        )

    if take_profit <= entry:
        return RiskResult(
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_per_unit=0.0,
            reward_per_unit=0.0,
            risk_reward=0.0,
            risk_amount=0.0,
            position_size=0.0,
            valid=False,
            reason="For a BUY setup, take-profit must be above entry.",
        )

    if account_balance <= 0:
        return RiskResult(
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_per_unit=0.0,
            reward_per_unit=0.0,
            risk_reward=0.0,
            risk_amount=0.0,
            position_size=0.0,
            valid=False,
            reason="Account balance must be greater than zero.",
        )

    if risk_percent <= 0:
        return RiskResult(
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_per_unit=0.0,
            reward_per_unit=0.0,
            risk_reward=0.0,
            risk_amount=0.0,
            position_size=0.0,
            valid=False,
            reason="Risk percentage must be greater than zero.",
        )

    risk_per_unit = entry - stop_loss
    reward_per_unit = take_profit - entry

    risk_reward = reward_per_unit / risk_per_unit

    risk_amount = account_balance * (risk_percent / 100.0)

    position_size = risk_amount / risk_per_unit

    return RiskResult(
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_per_unit=risk_per_unit,
        reward_per_unit=reward_per_unit,
        risk_reward=risk_reward,
        risk_amount=risk_amount,
        position_size=position_size,
        valid=True,
        reason="Risk calculation is valid.",
    )
