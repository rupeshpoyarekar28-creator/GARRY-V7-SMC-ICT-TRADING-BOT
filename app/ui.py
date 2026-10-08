"""
GARRY V7 SMC ICT TRADING BOT

Professional responsive dashboard UI.

UI ONLY:
- No SMC/ICT logic changes
- No Delta API changes
- No trading engine changes
- No build configuration changes
"""

from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

from app.state import AppState


class DashboardUI(BoxLayout):
    """Responsive main dashboard screen for GARRY V7."""

    def __init__(self, state: AppState, **kwargs):
        super().__init__(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(8),
            **kwargs,
        )

        self.state = state

        self._build_dashboard()

    # =========================================================
    # LABEL HELPERS
    # =========================================================

    def _label(
        self,
        text="",
        font_size=16,
        bold=False,
        halign="left",
    ):
        """Create a responsive dashboard label."""

        label = Label(
            text=str(text),
            font_size=sp(font_size),
            bold=bold,
            color=(1, 1, 1, 1),
            halign=halign,
            valign="middle",
            padding=(dp(4), 0),
            shorten=False,
            max_lines=1,
        )

        # Important:
        # text_size follows the actual widget width so
        # horizontal alignment works correctly.
        label.bind(
            size=lambda instance, value: setattr(
                instance,
                "text_size",
                (instance.width - dp(8), instance.height),
            )
        )

        return label

    # =========================================================
    # SECTION HEADING
    # =========================================================

    def _section_heading(self, text):
        """Create a clear section heading."""

        heading = self._label(
            text=text,
            font_size=17,
            bold=True,
            halign="left",
        )

        heading.size_hint_y = None
        heading.height = dp(38)

        return heading

    # =========================================================
    # DATA ROW
    # =========================================================

    def _data_row(
        self,
        label_text,
        value_text,
    ):
        """
        Create one independent label/value row.

        LEFT  = label
        RIGHT = value

        No fixed screen coordinates are used.
        """

        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(38),
            spacing=dp(6),
        )

        label = self._label(
            label_text,
            font_size=15,
            halign="left",
        )

        value = self._label(
            value_text,
            font_size=15,
            bold=True,
            halign="right",
        )

        # Independent columns.
        label.size_hint_x = 0.58
        value.size_hint_x = 0.42

        row.add_widget(label)
        row.add_widget(value)

        return row

    # =========================================================
    # SECTION CONTAINER
    # =========================================================

    def _section(
        self,
        heading,
        rows,
    ):
        """Create a complete dashboard section."""

        container = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(2),
        )

        container.add_widget(
            self._section_heading(heading)
        )

        for label_text, value_text in rows:

            container.add_widget(
                self._data_row(
                    label_text,
                    value_text,
                )
            )

        # Heading + rows
        container.height = (
            dp(38)
            + len(rows) * dp(40)
        )

        return container

    # =========================================================
    # DASHBOARD
    # =========================================================

    def _build_dashboard(self):
        """Build professional responsive dashboard."""

        # -----------------------------------------------------
        # SCROLL CONTAINER
        # -----------------------------------------------------

        scroll = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(4),
        )

        content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=dp(2),
        )

        # Make content height follow its children.
        content.bind(
            minimum_height=content.setter(
                "height"
            )
        )

        # -----------------------------------------------------
        # HEADER
        # -----------------------------------------------------

        header = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(82),
            spacing=dp(1),
        )

        title = self._label(
            "GARRY V7",
            font_size=25,
            bold=True,
            halign="center",
        )

        subtitle = self._label(
            "SMC / ICT TRADING BOT",
            font_size=16,
            bold=True,
            halign="center",
        )

        header.add_widget(title)
        header.add_widget(subtitle)

        content.add_widget(header)

        # -----------------------------------------------------
        # CONNECTION / MODE
        # -----------------------------------------------------

        connection_section = self._section(
            "CONNECTION",
            [
                (
                    "Connection",
                    self.state.connection_status,
                ),
                (
                    "Mode",
                    "ANALYSIS ONLY",
                ),
            ],
        )

        content.add_widget(
            connection_section
        )

        # -----------------------------------------------------
        # MARKET DATA
        # -----------------------------------------------------

        market_section = self._section(
            "MARKET DATA",
            [
                (
                    "Symbol",
                    self.state.symbol,
                ),
                (
                    "Price",
                    f"{self.state.price:.2f}",
                ),
                (
                    "Timeframe",
                    self.state.timeframe,
                ),
                (
                    "Trading",
                    (
                        "ENABLED"
                        if self.state.trading_enabled
                        else "DISABLED"
                    ),
                ),
            ],
        )

        content.add_widget(
            market_section
        )

        # -----------------------------------------------------
        # SMC / ICT ANALYSIS
        # -----------------------------------------------------

        analysis_section = self._section(
            "SMC / ICT ANALYSIS",
            [
                (
                    "Market Structure",
                    self.state.market_structure,
                ),
                (
                    "Signal",
                    self.state.signal,
                ),
                (
                    "Entry",
                    f"{self.state.entry:.2f}",
                ),
                (
                    "Stop Loss",
                    f"{self.state.stop_loss:.2f}",
                ),
                (
                    "Take Profit",
                    f"{self.state.take_profit:.2f}",
                ),
                (
                    "Risk",
                    f"{self.state.risk_percent:.2f}%",
                ),
                (
                    "Risk : Reward",
                    "--",
                ),
            ],
        )

        content.add_widget(
            analysis_section
        )

        # -----------------------------------------------------
        # STATUS
        # -----------------------------------------------------

        status_section = self._section(
            "STATUS",
            [
                (
                    "System",
                    "DEMO MODE",
                ),
                (
                    "Operation",
                    "ANALYSIS ONLY",
                ),
                (
                    "Orders",
                    "NO REAL ORDERS",
                ),
            ],
        )

        content.add_widget(
            status_section
        )

        # -----------------------------------------------------
        # BOTTOM SPACING
        # -----------------------------------------------------

        bottom_space = BoxLayout(
            size_hint_y=None,
            height=dp(12),
        )

        content.add_widget(
            bottom_space
        )

        scroll.add_widget(content)

        self.add_widget(scroll)
