
"""
GARRY V7 — Unified PAPER / LIVE Execution Router

Path: strategy/execution_router.py

PAPER is the default mode.
LIVE orders remain blocked until a verified live adapter is supplied
and the operator explicitly arms LIVE trading.
"""

from dataclasses import dataclass
from typing import Any, Literal, Optional, Protocol

from strategy.paper_trading import PaperTrader


ExecutionMode = Literal["PAPER", "LIVE"]
TradeSignal = Literal["BUY", "SELL", "NO TRADE"]

DEFAULT_TP_POINTS = 20.0
DEFAULT_SL_POINTS = 15.0
MAX_TRADES_PER_DAY = 4


class ExecutionRouterError(RuntimeError):
    """Base error for execution routing."""


class LiveTradingNotReady(ExecutionRouterError):
    """Raised when safe, verified LIVE execution is unavailable."""


class LiveExecutionAdapter(Protocol):
    """
    A future Delta private-API adapter must implement this method.

    It must validate the contract and quantity, submit the entry order,
    place exchange-side protective SL/TP orders, and handle order failures.
    """

    def place_protected_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss: float,
        take_profit: float,
        client_order_id: str,
    ) -> Any:
        ...


@dataclass(frozen=True)
class ExecutionResult:
    mode: str
    status: str
    symbol: str
    side: str
    entry: float
    stop_loss: float
    take_profit: float
    details: Any = None


class ExecutionRouter:
    """Routes signals to PAPER or a verified LIVE adapter."""

    def __init__(
        self,
        paper_trader: Optional[PaperTrader] = None,
        live_adapter: Optional[LiveExecutionAdapter] = None,
        tp_points: float = DEFAULT_TP_POINTS,
        sl_points: float = DEFAULT_SL_POINTS,
        max_trades_per_day: int = MAX_TRADES_PER_DAY,
    ):
        if tp_points <= 0 or sl_points <= 0:
            raise ValueError("TP and SL points must be greater than zero.")
        if max_trades_per_day != 4:
            raise ValueError("GARRY V7 daily trade limit is fixed at 4.")

        self.paper_trader = paper_trader or PaperTrader()
        self.live_adapter = live_adapter

        # PAPER is always the initial mode.
        self.mode: ExecutionMode = "PAPER"
        self.live_armed = False
        self.trading_enabled = True

        self.tp_points = float(tp_points)
        self.sl_points = float(sl_points)
        self.max_trades_per_day = max_trades_per_day

    def set_mode(self, mode: ExecutionMode) -> None:
        """Change mode; switching to LIVE does not arm real orders."""
        if mode not in ("PAPER", "LIVE"):
            raise ValueError("Mode must be PAPER or LIVE.")

        self.mode = mode

        # Disarm LIVE every time the mode is changed.
        self.live_armed = False

    def arm_live(self, confirmation: str) -> None:
        """
        Explicit LIVE arming. This is not available until a real adapter
        has been supplied and independently verified.
        """
        if self.live_adapter is None:
            raise LiveTradingNotReady(
                "LIVE blocked: verified Delta private-API adapter "
                "is not installed."
            )

        if confirmation != "ENABLE LIVE TRADING":
            raise LiveTradingNotReady(
                'Type the exact confirmation: "ENABLE LIVE TRADING".'
            )

        self.mode = "LIVE"
        self.live_armed = True

    def disarm_live(self) -> None:
        self.live_armed = False
        self.trading_enabled = False

    def enable_trading(self) -> None:
        self.trading_enabled = True

    def execute_signal(
        self,
        *,
        symbol: str,
        signal: TradeSignal,
        entry: float,
        quantity: float = 1.0,
        client_order_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute a validated BUY/SELL signal in the selected mode."""

        if not self.trading_enabled:
            raise ExecutionRouterError("Trading is stopped.")

        if signal == "NO TRADE":
            return ExecutionResult(
                mode=self.mode,
                status="SKIPPED",
                symbol=symbol,
                side=signal,
                entry=float(entry),
                stop_loss=0.0,
                take_profit=0.0,
                details="No trade signal.",
            )

        if signal not in ("BUY", "SELL"):
            raise ValueError("Signal must be BUY, SELL, or NO TRADE.")

        if not symbol or entry <= 0 or quantity <= 0:
            raise ValueError("Symbol, entry, and quantity must be valid.")

        entry = float(entry)
        quantity = float(quantity)

        if signal == "BUY":
            stop_loss = entry - self.sl_points
            take_profit = entry + self.tp_points
        else:
            stop_loss = entry + self.sl_points
            take_profit = entry - self.tp_points

        if stop_loss <= 0 or take_profit <= 0:
            raise ValueError("Calculated SL/TP is invalid.")

        if self.mode == "PAPER":
            # Existing PaperTrader applies its own fixed 15/20 point
            # rules and daily limit. It does not place exchange orders.
            trade = self.paper_trader.open_position(
                symbol=symbol,
                side=signal,
                entry=entry,
                quantity=quantity,
            )

            return ExecutionResult(
                mode="PAPER",
                status="PAPER_POSITION_OPENED",
                symbol=symbol,
                side=signal,
                entry=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                details=trade,
            )

        # Fail closed: no real orders without explicit arming and
        # a verified private API adapter.
        if not self.live_armed or self.live_adapter is None:
            raise LiveTradingNotReady(
                "LIVE order blocked. Verify the Delta adapter and "
                "explicitly arm LIVE trading first."
            )

        if not client_order_id:
            raise LiveTradingNotReady(
                "LIVE order blocked: a unique client_order_id is required."
            )

        result = self.live_adapter.place_protected_order(
            symbol=symbol,
            side=signal,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            client_order_id=client_order_id,
        )

        return ExecutionResult(
            mode="LIVE",
            status="ORDER_SUBMITTED",
            symbol=symbol,
            side=signal,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            details=result,
        )
