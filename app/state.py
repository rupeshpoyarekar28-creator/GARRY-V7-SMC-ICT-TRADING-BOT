"""
GARRY V7 SMC ICT TRADING BOT

Application runtime state.
"""

from dataclasses import dataclass


APPROVED_SYMBOLS = (
    "BTCUSD",
    "XAUTUSD",
    "ETHUSD",
    "PAXGUSD",
    "SOLUSD",
    "XRPUSD",
    "UNIUSD",
)


@dataclass
class AppState:
    symbol: str = "BTCUSD"
    price: float = 0.0
    timeframe: str = "5m"
    connection_status: str = "NOT CONNECTED"
    market_structure: str = "WAITING"
    signal: str = "NO TRADE"
    entry: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_percent: float = 1.0
    trading_enabled: bool = False


def create_default_state() -> AppState:
    return AppState()
