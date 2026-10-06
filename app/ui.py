"""
GARRY V7 SMC ICT TRADING BOT

Clean dashboard UI.

This module is independent of the old GARRY V8 project.
Real trading execution is not implemented here.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label

from app.state import AppState


class DashboardUI(BoxLayout):
    """Main dashboard screen for GARRY V7."""

    def __init__(self, state: AppState, **kwargs):
        super().__init__(
            orientation="vertical",
            padding=20,
            spacing=12,
            **kwargs,
        )

        self.state = state
        self._build_dashboard()

    def _create_label(
        self,
        text: str,
        font_size: str = "16sp",
        bold: bool = False,
    ) -> Label:
        """Create a consistently configured dashboard label."""
        return Label(
            text=text,
            font_size=font_size,
            bold=bold,
            halign="left",
            valign="middle",
        )

    def _build_dashboard(self) -> None:
        """Build the complete dashboard layout."""

        title = self._create_label(
            "GARRY V7 SMC ICT TRADING BOT",
            font_size="24sp",
            bold=True,
        )
        title.size_hint_y = None
        title.height = 60
        title.halign = "center"

        self.add_widget(title)

        connection = self._create_label(
            f"Connection: {self.state.connection_status}"
        )
        self.add_widget(connection)

        market_grid = GridLayout(
            cols=2,
            spacing=8,
            size_hint_y=None,
            height=150,
        )

        market_grid.add_widget(self._create_label("Symbol"))
        market_grid.add_widget(
            self._create_label(self.state.symbol)
        )

        market_grid.add_widget(self._create_label("Price"))
        market_grid.add_widget(
            self._create_label(f"{self.state.price:.2f}")
        )

        market_grid.add_widget(self._create_label("Timeframe"))
        market_grid.add_widget(
            self._create_label(self.state.timeframe)
        )

        market_grid.add_widget(self._create_label("Trading"))
        market_grid.add_widget(
            self._create_label(
                "DISABLED" if not self.state.trading_enabled else "ENABLED"
            )
        )

        self.add_widget(market_grid)

        analysis_title = self._create_label(
            "SMC / ICT ANALYSIS",
            font_size="20sp",
            bold=True,
        )
        analysis_title.size_hint_y = None
        analysis_title.height = 45
        self.add_widget(analysis_title)

        analysis_grid = GridLayout(
            cols=2,
            spacing=8,
            size_hint_y=None,
            height=180,
        )

        analysis_grid.add_widget(
            self._create_label("Market Structure")
        )
        analysis_grid.add_widget(
            self._create_label(self.state.market_structure)
        )

        analysis_grid.add_widget(
            self._create_label("Signal")
        )
        analysis_grid.add_widget(
            self._create_label(self.state.signal)
        )

        analysis_grid.add_widget(
            self._create_label("Entry")
        )
        analysis_grid.add_widget(
            self._create_label(f"{self.state.entry:.2f}")
        )

        analysis_grid.add_widget(
            self._create_label("Stop Loss")
        )
        analysis_grid.add_widget(
            self._create_label(f"{self.state.stop_loss:.2f}")
        )

        analysis_grid.add_widget(
            self._create_label("Take Profit")
        )
        analysis_grid.add_widget(
            self._create_label(f"{self.state.take_profit:.2f}")
        )

        analysis_grid.add_widget(
            self._create_label("Risk")
        )
        analysis_grid.add_widget(
            self._create_label(f"{self.state.risk_percent:.2f}%")
        )

        self.add_widget(analysis_grid)

        footer = self._create_label(
            "DEMO MODE • ANALYSIS ONLY • NO REAL ORDERS",
            font_size="14sp",
        )
        footer.size_hint_y = None
        footer.height = 45
        footer.halign = "center"

        self.add_widget(footer)
