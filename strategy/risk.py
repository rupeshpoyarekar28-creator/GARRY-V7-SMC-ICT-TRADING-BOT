"""
GARRY V7 SMC ICT TRADING BOT
Risk and Money Management Engine.

Rules:
- Risk per trade: 1%
- Maximum trades per day: 4
- Maximum daily risk: 4%
- No forced trade
- BUY and SELL supported
- Contract/tick-aware position sizing
- Fee/funding buffer supported
- Invalid risk parameters => NO TRADE

IMPORTANT:
This module calculates risk only.
It does NOT place exchange orders.
"""

from dataclasses import dataclass
from math import floor, isfinite


@dataclass
class RiskConfig:
    # Final user-defined money management
    risk_percent_per_trade: float = 1.0
    max_trades_per_day: int = 4
    max_daily_risk_percent: float = 4.0

    # Trading-cost protection
    fee_buffer_percent: float = 0.10
    funding_buffer_percent: float = 0.10

    # Minimum quantity protection
    min_quantity: float = 0.0

    # Quantity precision
    quantity_step: float = 1.0


@dataclass
class RiskResult:
    valid: bool
    reason: str
    risk_amount: float = 0.0
    price_risk: float = 0.0
    quantity: float = 0.0
    estimated_fee_buffer: float = 0.0
    estimated_funding_buffer: float = 0.0
    estimated_total_risk: float = 0.0
    risk_percent: float = 0.0


class RiskEngine:
    """Risk calculation only; this class never places orders."""

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()
        self.trades_today = 0
        self.daily_risk_used_percent = 0.0

    def reset_daily_limits(self):
        """Reset counters when a new trading day is confirmed."""
        self.trades_today = 0
        self.daily_risk_used_percent = 0.0

    def register_trade(self, risk_percent: float):
        """Call once for each accepted trade, not for rejected signals."""
        if not isfinite(risk_percent) or risk_percent <= 0:
            return
        self.trades_today += 1
        self.daily_risk_used_percent += risk_percent

    def can_trade(self) -> tuple[bool, str]:
        if self.trades_today >= self.config.max_trades_per_day:
            return False, "MAX DAILY TRADES REACHED"

        remaining = (
            self.config.max_daily_risk_percent
            - self.daily_risk_used_percent
        )
        if remaining <= 0:
            return False, "MAX DAILY RISK REACHED"

        return True, "RISK LIMIT OK"

    def calculate_position_size(
        self,
        balance: float,
        entry: float,
        stop_loss: float,
        side: str,
        contract_value: float = 1.0,
        quantity_step: float | None = None,
        min_quantity: float | None = None,
    ) -> RiskResult:
        side = str(side).upper().strip()

        # Validate configuration
        cfg = self.config
        numeric_config = (
            cfg.risk_percent_per_trade,
            cfg.max_daily_risk_percent,
            cfg.fee_buffer_percent,
            cfg.funding_buffer_percent,
            cfg.quantity_step,
            cfg.min_quantity,
            cfg.max_trades_per_day,
        )
        if not all(isfinite(float(x)) for x in numeric_config):
            return self._invalid("INVALID RISK CONFIGURATION")

        if (
            cfg.risk_percent_per_trade <= 0
            or cfg.max_trades_per_day < 1
            or cfg.max_daily_risk_percent <= 0
            or cfg.fee_buffer_percent < 0
            or cfg.funding_buffer_percent < 0
            or cfg.quantity_step <= 0
            or cfg.min_quantity < 0
        ):
            return self._invalid("INVALID RISK CONFIGURATION")

        # Validate trade inputs
        values = (balance, entry, stop_loss, contract_value)
        if not all(isfinite(float(x)) for x in values):
            return self._invalid("NON-FINITE TRADE INPUT")

        if balance <= 0:
            return self._invalid("INVALID ACCOUNT BALANCE")
        if entry <= 0:
            return self._invalid("INVALID ENTRY PRICE")
        if stop_loss <= 0:
            return self._invalid("INVALID STOP LOSS")
        if contract_value <= 0:
            return self._invalid("INVALID CONTRACT VALUE")
        if side not in ("BUY", "SELL"):
            return self._invalid("INVALID TRADE SIDE")

        if side == "BUY" and stop_loss >= entry:
            return self._invalid(
                "INVALID BUY SL: STOP LOSS MUST BE BELOW ENTRY"
            )
        if side == "SELL" and stop_loss <= entry:
            return self._invalid(
                "INVALID SELL SL: STOP LOSS MUST BE ABOVE ENTRY"
            )

        allowed, reason = self.can_trade()
        if not allowed:
            return self._invalid(reason)

        remaining = (
            cfg.max_daily_risk_percent
            - self.daily_risk_used_percent
        )
        allowed_risk_percent = min(
            cfg.risk_percent_per_trade,
            remaining,
        )
        if allowed_risk_percent <= 0:
            return self._invalid("NO DAILY RISK REMAINING")

        risk_amount = balance * allowed_risk_percent / 100.0
        price_risk = abs(entry - stop_loss)
        if price_risk <= 0:
            return self._invalid("ZERO STOP LOSS DISTANCE")

        raw_quantity = risk_amount / (price_risk * contract_value)
        if not isfinite(raw_quantity) or raw_quantity <= 0:
            return self._invalid("CALCULATED QUANTITY IS ZERO")

        step = (
            quantity_step
            if quantity_step is not None
            else cfg.quantity_step
        )
        minimum = (
            min_quantity
            if min_quantity is not None
            else cfg.min_quantity
        )

        if (
            not isfinite(float(step))
            or not isfinite(float(minimum))
            or step <= 0
            or minimum < 0
        ):
            return self._invalid("INVALID QUANTITY SETTINGS")

        quantity = floor((raw_quantity + 1e-12) / step) * step
        quantity = self._round_quantity(quantity, step)

        if quantity <= 0:
            return self._invalid(
                "QUANTITY BECAME ZERO AFTER ROUNDING"
            )
        if minimum > 0 and quantity < minimum:
            return self._invalid(
                "CALCULATED QUANTITY BELOW EXCHANGE MINIMUM"
            )

        fee_buffer = risk_amount * cfg.fee_buffer_percent / 100.0
        funding_buffer = (
            risk_amount * cfg.funding_buffer_percent / 100.0
        )

        return RiskResult(
            valid=True,
            reason="RISK CHECK PASSED",
            risk_amount=risk_amount,
            price_risk=price_risk,
            quantity=quantity,
            estimated_fee_buffer=fee_buffer,
            estimated_funding_buffer=funding_buffer,
            estimated_total_risk=(
                risk_amount + fee_buffer + funding_buffer
            ),
            risk_percent=allowed_risk_percent,
        )

    def validate_trade(
        self,
        balance: float,
        entry: float,
        stop_loss: float,
        side: str,
        contract_value: float = 1.0,
        quantity_step: float | None = None,
        min_quantity: float | None = None,
    ) -> RiskResult:
        return self.calculate_position_size(
            balance=balance,
            entry=entry,
            stop_loss=stop_loss,
            side=side,
            contract_value=contract_value,
            quantity_step=quantity_step,
            min_quantity=min_quantity,
        )

    @staticmethod
    def _round_quantity(value: float, step: float) -> float:
        if step >= 1:
            return float(int(value))

        decimals = 0
        temp = step
        while temp < 1 and decimals < 12:
            temp *= 10
            decimals += 1

        return round(value, decimals)

    @staticmethod
    def _invalid(reason: str) -> RiskResult:
        return RiskResult(valid=False, reason=reason)
