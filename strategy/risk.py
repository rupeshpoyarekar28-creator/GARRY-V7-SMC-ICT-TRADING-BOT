"""
GARRY V7 SMC ICT TRADING BOT

Risk and Money Management Engine.

Rules:
- Risk per trade: 1%
- Maximum trades per day: 2
- Maximum daily risk: 2%
- No forced trade
- BUY and SELL supported
- Contract/tick aware position sizing
- Fee/funding buffer supported
- Invalid risk parameters => NO TRADE
- Analysis/Paper/Live can use the same risk engine

IMPORTANT:
This module calculates risk only.
It does NOT place orders.
"""

from dataclasses import dataclass
from math import floor


@dataclass
class RiskConfig:
    # User-defined money management
    risk_percent_per_trade: float = 1.0
    max_trades_per_day: int = 2
    max_daily_risk_percent: float = 2.0

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
    """
    Central money-management engine.

    The engine does not execute orders.
    It only decides whether a trade is allowed from a risk perspective
    and calculates the maximum safe quantity.
    """

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()

        self.trades_today = 0
        self.daily_risk_used_percent = 0.0

    # ------------------------------------------------------------------
    # Daily limits
    # ------------------------------------------------------------------

    def reset_daily_limits(self):
        """Reset counters at the beginning of a new trading day."""
        self.trades_today = 0
        self.daily_risk_used_percent = 0.0

    def register_trade(self, risk_percent: float):
        """
        Register a trade only after the order/trade is actually accepted.
        """
        if risk_percent <= 0:
            return

        self.trades_today += 1
        self.daily_risk_used_percent += risk_percent

    def can_trade(self) -> tuple[bool, str]:
        """
        Check hard daily trading limits.
        """

        if self.trades_today >= self.config.max_trades_per_day:
            return False, "MAX DAILY TRADES REACHED"

        remaining_risk = (
            self.config.max_daily_risk_percent
            - self.daily_risk_used_percent
        )

        if remaining_risk <= 0:
            return False, "MAX DAILY RISK REACHED"

        return True, "RISK LIMIT OK"

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

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
        """
        Calculate safe position quantity.

        Parameters
        ----------
        balance:
            Available/equity value used for risk calculation.

        entry:
            Planned entry price.

        stop_loss:
            Planned stop-loss price.

        side:
            BUY or SELL.

        contract_value:
            Currency value represented by one contract/unit
            for the price movement.

        quantity_step:
            Minimum quantity increment.

        min_quantity:
            Exchange minimum quantity.

        Returns
        -------
        RiskResult
        """

        side = str(side).upper().strip()

        # --------------------------------------------------------------
        # Basic validation
        # --------------------------------------------------------------

        if balance <= 0:
            return self._invalid("INVALID ACCOUNT BALANCE")

        if entry <= 0:
            return self._invalid("INVALID ENTRY PRICE")

        if stop_loss <= 0:
            return self._invalid("INVALID STOP LOSS")

        if side not in ("BUY", "SELL"):
            return self._invalid("INVALID TRADE SIDE")

        if contract_value <= 0:
            return self._invalid("INVALID CONTRACT VALUE")

        # --------------------------------------------------------------
        # Direction validation
        # --------------------------------------------------------------

        if side == "BUY" and stop_loss >= entry:
            return self._invalid(
                "INVALID BUY SL: STOP LOSS MUST BE BELOW ENTRY"
            )

        if side == "SELL" and stop_loss <= entry:
            return self._invalid(
                "INVALID SELL SL: STOP LOSS MUST BE ABOVE ENTRY"
            )

        # --------------------------------------------------------------
        # Daily limits
        # --------------------------------------------------------------

        allowed, reason = self.can_trade()

        if not allowed:
            return self._invalid(reason)

        remaining_daily_risk = (
            self.config.max_daily_risk_percent
            - self.daily_risk_used_percent
        )

        allowed_risk_percent = min(
            self.config.risk_percent_per_trade,
            remaining_daily_risk,
        )

        if allowed_risk_percent <= 0:
            return self._invalid("NO DAILY RISK REMAINING")

        # --------------------------------------------------------------
        # Risk amount
        # --------------------------------------------------------------

        risk_amount = balance * (
            allowed_risk_percent / 100.0
        )

        price_risk = abs(entry - stop_loss)

        if price_risk <= 0:
            return self._invalid("ZERO STOP LOSS DISTANCE")

        # --------------------------------------------------------------
        # Raw position size
        #
        # Approximate loss:
        #
        # price movement × contract value × quantity
        #
        # --------------------------------------------------------------

        raw_quantity = risk_amount / (
            price_risk * contract_value
        )

        if raw_quantity <= 0:
            return self._invalid("CALCULATED QUANTITY IS ZERO")

        # --------------------------------------------------------------
        # Quantity step
        # --------------------------------------------------------------

        step = (
            quantity_step
            if quantity_step is not None
            else self.config.quantity_step
        )

        if step <= 0:
            step = 1.0

        quantity = floor(raw_quantity / step) * step

        # Avoid floating-point artifacts.
        quantity = self._round_quantity(quantity, step)

        minimum_quantity = (
            min_quantity
            if min_quantity is not None
            else self.config.min_quantity
        )

        if minimum_quantity > 0 and quantity < minimum_quantity:
            return self._invalid(
                "CALCULATED QUANTITY BELOW EXCHANGE MINIMUM"
            )

        if quantity <= 0:
            return self._invalid(
                "QUANTITY BECAME ZERO AFTER ROUNDING"
            )

        # --------------------------------------------------------------
        # Cost buffers
        # --------------------------------------------------------------

        fee_buffer = (
            risk_amount
            * self.config.fee_buffer_percent
            / 100.0
        )

        funding_buffer = (
            risk_amount
            * self.config.funding_buffer_percent
            / 100.0
        )

        estimated_total_risk = (
            risk_amount
            + fee_buffer
            + funding_buffer
        )

        return RiskResult(
            valid=True,
            reason="RISK CHECK PASSED",
            risk_amount=risk_amount,
            price_risk=price_risk,
            quantity=quantity,
            estimated_fee_buffer=fee_buffer,
            estimated_funding_buffer=funding_buffer,
            estimated_total_risk=estimated_total_risk,
            risk_percent=allowed_risk_percent,
        )

    # ------------------------------------------------------------------
    # Convenience method
    # ------------------------------------------------------------------

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
        """
        Alias used by strategy/signal code.
        """

        return self.calculate_position_size(
            balance=balance,
            entry=entry,
            stop_loss=stop_loss,
            side=side,
            contract_value=contract_value,
            quantity_step=quantity_step,
            min_quantity=min_quantity,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _round_quantity(value: float, step: float) -> float:
        """
        Round quantity according to exchange quantity step.
        """
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
        """
        Return a failed risk result.
        """
        return RiskResult(
            valid=False,
            reason=reason,
        )
