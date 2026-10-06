"""
GARRY V7 SMC ICT TRADING BOT

Application state definitions.

This module contains only simple application state.
It has no dependency on the old GARRY V8 project.
"""

from dataclasses import dataclass


@dataclass
class AppState:
    """Runtime state for the GARRY V7 application."""

    symbol: str = "BTCUSDT"
    price: float = 0.0
    timeframe: str = "5m"
    connection_status: str = "DEMO"
    market_structure: str = "WAITING"
    signal: str = "NO TRADE"
    entry: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_percent: float = 1.0
    trading_enabled: bool = False


def create_default_state() -> AppState:
    """
    Create a fresh default application state.

    Real trading is disabled by default.
    """
    return AppState()
