"""
GARRY V7 SMC ICT TRADING BOT
Professional dark trading dashboard UI.
"""

from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from app.state import APPROVED_SYMBOLS, AppState


BG = (0.025, 0.023, 0.035, 1)
CARD = (0.075, 0.070, 0.095, 1)
CARD2 = (0.105, 0.095, 0.135, 1)

WHITE = (0.96, 0.95, 1, 1)
MUTED = (0.58, 0.56, 0.65, 1)

PURPLE = (0.48, 0.28, 0.95, 1)
PURPLE_LIGHT = (0.67, 0.52, 1, 1)

GREEN = (0.20, 0.85, 0.48, 1)
RED = (0.95, 0.25, 0.32, 1)
ORANGE = (1.0, 0.62, 0.20, 1)


class Card(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.padding = dp(14)

        with self.canvas.before:
            Color(*CARD)
            self.bg = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(16)]
            )

        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *_):
        self.bg.pos = self.pos
        self.bg.size = self.size


class DashboardUI(BoxLayout):

    def __init__(self, state: AppState, **kwargs):

        super().__init__(
            orientation="vertical",
            spacing=0,
            **kwargs
        )

        self.state = state
        self.current_page = "HOME"

        with self.canvas.before:
            Color(*BG)
            self.background = RoundedRectangle(
                pos=self.pos,
                size=self.size
            )

        self.bind(
            pos=self._update_background,
            size=self._update_background
        )

        self.page = BoxLayout(
            orientation="vertical"
        )

        self.add_widget(self.page)

        self.navigation = self.build_navigation()

        self.add_widget(self.navigation)

        self.show_home()

    def _update_background(self, *_):

        self.background.pos = self.pos
        self.background.size = self.size

    # ---------------------------------------------------------
    # BASIC UI HELPERS
    # ---------------------------------------------------------

    def label(
        self,
        text,
        size=14,
        bold=False,
        color=WHITE,
        align="left"
    ):

        widget = Label(
            text=str(text),
            font_size=sp(size),
            bold=bold,
            color=color,
            halign=align,
            valign="middle"
        )

        widget.bind(
            size=lambda instance, value:
            setattr(instance, "text_size", value)
        )

        return widget

    def button(
        self,
        text,
        height=48,
        accent=False
    ):

        button = Button(
            text=text,
            size_hint_y=None,
            height=dp(height),
            font_size=sp(14),
            bold=True,
            color=WHITE,
            background_normal="",
            background_down="",
            background_color=(
                PURPLE if accent else CARD2
            ),
            border=(0, 0, 0, 0)
        )

        return button

    def clear_page(self):

        self.page.clear_widgets()

    def scroll_container(self):

        scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(3)
        )

        container = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=(
                dp(14),
                dp(12),
                dp(14),
                dp(20)
            ),
            spacing=dp(12)
        )

        container.bind(
            minimum_height=container.setter("height")
        )

        scroll.add_widget(container)

        self.page.add_widget(scroll)

        return container

    # ---------------------------------------------------------
    # HEADER
    # ---------------------------------------------------------

    def header(self, title, subtitle=""):

        box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(72)
        )

        box.add_widget(
            self.label(
                title,
                26,
                True
            )
        )

        if subtitle:

            box.add_widget(
                self.label(
                    subtitle,
                    12,
                    True,
                    PURPLE_LIGHT
                )
            )

        return box

    # ---------------------------------------------------------
    # BOTTOM NAVIGATION
    # ---------------------------------------------------------

    def build_navigation(self):

        navigation = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(68),
            padding=dp(6),
            spacing=dp(4)
        )

        pages = [
            ("HOME", "⌂\nHome"),
            ("MARKETS", "◈\nMarkets"),
            ("TRADES", "▣\nTrades"),
            ("ANALYSIS", "⌁\nAnalysis"),
            ("SETTINGS", "⚙\nSettings")
        ]

        for page_name, text in pages:

            button = Button(
                text=text,
                font_size=sp(11),
                color=(
                    PURPLE_LIGHT
                    if page_name == self.current_page
                    else MUTED
                ),
                background_normal="",
                background_color=BG,
                border=(0, 0, 0, 0)
            )

            button.bind(
                on_release=lambda _, p=page_name:
                self.navigate(p)
            )

            navigation.add_widget(button)

        return navigation

    def refresh_navigation(self):

        pages = [
            "HOME",
            "MARKETS",
            "TRADES",
            "ANALYSIS",
            "SETTINGS"
        ]

        for index, child in enumerate(
            reversed(self.navigation.children)
        ):

            child.color = (
                PURPLE_LIGHT
                if pages[index] == self.current_page
                else MUTED
            )

    def navigate(self, page):

        self.current_page = page

        if page == "HOME":
            self.show_home()

        elif page == "MARKETS":
            self.show_markets()

        elif page == "TRADES":
            self.show_trades()

        elif page == "ANALYSIS":
            self.show_analysis()

        elif page == "SETTINGS":
            self.show_settings()

        self.refresh_navigation()

    # ---------------------------------------------------------
    # HOME
    # ---------------------------------------------------------

    def show_home(self):

        self.clear_page()

        container = self.scroll_container()

        container.add_widget(
            self.header(
                "GARRY V7",
                "SMC / ICT TRADING BOT"
            )
        )

        # SYSTEM CARD

        system = Card(
            size_hint_y=None,
            height=dp(82)
        )

        status_box = BoxLayout(
            orientation="vertical"
        )

        status_box.add_widget(
            self.label(
                "SYSTEM STATUS",
                10,
                False,
                MUTED
            )
        )

        status_box.add_widget(
            self.label(
                "NOT CONNECTED",
                18,
                True,
                ORANGE
            )
        )

        system.add_widget(status_box)

        engine = self.label(
            "●  ENGINE READY",
            12,
            True,
            GREEN,
            "right"
        )

        system.add_widget(engine)

        container.add_widget(system)

        # MARKET CARD

        market = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(255)
        )

        top_row = BoxLayout(
            size_hint_y=None,
            height=dp(42)
        )

        top_row.add_widget(
            self.label(
                "MARKET",
                12,
                True,
                MUTED
            )
        )

        selector = Spinner(
            text=self.state.symbol,
            values=APPROVED_SYMBOLS,
            size_hint_x=None,
            width=dp(125),
            background_normal="",
            background_color=CARD2,
            color=WHITE
        )

        selector.bind(
            text=self.change_symbol
        )

        top_row.add_widget(selector)

        market.add_widget(top_row)

        market.add_widget(
            self.label(
                "LIVE DATA PENDING",
                28,
                True,
                WHITE,
                "center"
            )
        )

        market.add_widget(
            self.label(
                "Delta Exchange India",
                12,
                False,
                MUTED,
                "center"
            )
        )

        stats = GridLayout(
            cols=3,
            spacing=dp(8),
            size_hint_y=None,
            height=dp(75)
        )

        for name in ["BID", "ASK", "24H"]:

            mini = Card(
                orientation="vertical",
                padding=dp(8)
            )

            mini.add_widget(
                self.label(
                    name,
                    10,
                    False,
                    MUTED
                )
            )

            mini.add_widget(
                self.label(
                    "--",
                    15,
                    True
                )
            )

            stats.add_widget(mini)

        market.add_widget(stats)

        container.add_widget(market)

        # SIGNAL CARD

        signal = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(145)
        )

        signal.add_widget(
            self.label(
                "CURRENT SIGNAL",
                11,
                True,
                MUTED
            )
        )

        signal.add_widget(
            self.label(
                "WAITING",
                28,
                True,
                WHITE,
                "center"
            )
        )

        signal.add_widget(
            self.label(
                "Waiting for valid SMC / ICT confirmation",
                12,
                False,
                MUTED,
                "center"
            )
        )

        container.add_widget(signal)

        # LEVELS

        levels = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(175)
        )

        levels.add_widget(
            self.label(
                "TRADE LEVELS",
                12,
                True,
                MUTED
            )
        )

        for name in [
            "ENTRY",
            "STOP LOSS",
            "TAKE PROFIT",
            "RISK",
            "R:R"
        ]:

            row = BoxLayout(
                size_hint_y=None,
                height=dp(27)
            )

            row.add_widget(
                self.label(
                    name,
                    12,
                    False,
                    MUTED
                )
            )

            row.add_widget(
                self.label(
                    "--",
                    12,
                    True,
                    WHITE,
                    "right"
                )
            )

            levels.add_widget(row)

        container.add_widget(levels)

        # STOP BOT

        stop = self.button(
            "STOP BOT",
            52
        )

        stop.color = RED

        container.add_widget(stop)

    def change_symbol(self, spinner, value):

        if value in APPROVED_SYMBOLS:

            self.state.symbol = value

    # ---------------------------------------------------------
    # MARKETS
    # ---------------------------------------------------------

    def show_markets(self):

        self.clear_page()

        container = self.scroll_container()

        container.add_widget(
            self.header(
                "MARKETS",
                "DELTA EXCHANGE INDIA"
            )
        )

        for symbol in APPROVED_SYMBOLS:

            card = Card(
                size_hint_y=None,
                height=dp(70)
            )

            card.add_widget(
                self.label(
                    symbol,
                    16,
                    True
                )
            )

            card.add_widget(
                self.label(
                    "LIVE DATA PENDING",
                    11,
                    False,
                    MUTED,
                    "right"
                )
            )

            container.add_widget(card)

    # ---------------------------------------------------------
    # TRADES
    # ---------------------------------------------------------

    def show_trades(self):

        self.clear_page()

        container = self.scroll_container()

        container.add_widget(
            self.header(
                "TRADES",
                "TRADE HISTORY & PERFORMANCE"
            )
        )

        statistics = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(190)
        )

        for name, value in [
            ("TOTAL TRADES", "0"),
            ("WINNING TRADES", "0"),
            ("LOSING TRADES", "0"),
            ("WIN RATE", "--"),
            ("NET P&L", "₹0.00")
        ]:

            row = BoxLayout(
                size_hint_y=None,
                height=dp(32)
            )

            row.add_widget(
                self.label(
                    name,
                    12,
                    False,
                    MUTED
                )
            )

            row.add_widget(
                self.label(
                    value,
                    13,
                    True,
                    WHITE,
                    "right"
                )
            )

            statistics.add_widget(row)

        container.add_widget(statistics)

        container.add_widget(
            self.label(
                "NO TRADES YET",
                14,
                True,
                MUTED,
                "center"
            )
        )

    # ---------------------------------------------------------
    # ANALYSIS
    # ---------------------------------------------------------

    def show_analysis(self):

        self.clear_page()

        container = self.scroll_container()

        container.add_widget(
            self.header(
                "ANALYSIS",
                "SMC / ICT MARKET STRUCTURE"
            )
        )

        analysis_items = [
            "MARKET STRUCTURE",
            "BOS / CHOCH",
            "LIQUIDITY SWEEP",
            "ORDER BLOCK",
            "FVG",
            "IDM",
            "DISPLACEMENT",
            "PREMIUM / DISCOUNT"
        ]

        for item in analysis_items:

            card = Card(
                size_hint_y=None,
                height=dp(58)
            )

            card.add_widget(
                self.label(
                    item,
                    12,
                    False,
                    MUTED
                )
            )

            card.add_widget(
                self.label(
                    "WAITING",
                    12,
                    True,
                    WHITE,
                    "right"
                )
            )

            container.add_widget(card)

    # ---------------------------------------------------------
    # SETTINGS
    # ---------------------------------------------------------

    def show_settings(self):

        self.clear_page()

        container = self.scroll_container()

        container.add_widget(
            self.header(
                "SETTINGS",
                "GARRY V7 CONFIGURATION"
            )
        )

        # API

        api = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(285)
        )

        api.add_widget(
            self.label(
                "DELTA API",
                16,
                True
            )
        )

        api.add_widget(
            self.label(
                "Trading-only credentials",
                11,
                False,
                MUTED
            )
        )

        key = TextInput(
            hint_text="API KEY",
            multiline=False,
            size_hint_y=None,
            height=dp(48),
            background_color=CARD2,
            foreground_color=WHITE,
            hint_text_color=MUTED
        )

        secret = TextInput(
            hint_text="API SECRET",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(48),
            background_color=CARD2,
            foreground_color=WHITE,
            hint_text_color=MUTED
        )

        api.add_widget(key)
        api.add_widget(secret)

        api.add_widget(
            self.label(
                "Never store API secrets in source code or logs.",
                10,
                False,
                MUTED
            )
        )

        buttons = BoxLayout(
            size_hint_y=None,
            height=dp(48),
            spacing=dp(8)
        )

        buttons.add_widget(
            self.button(
                "SAVE",
                48,
                True
            )
        )

        buttons.add_widget(
            self.button(
                "TEST",
                48
            )
        )

        api.add_widget(buttons)

        container.add_widget(api)

        # MODE

        mode = Card(
            orientation="vertical",
            size_hint_y=None,
            height=dp(165)
        )

        mode.add_widget(
            self.label(
                "TRADING MODE",
                14,
                True
            )
        )

        mode.add_widget(
            self.label(
                "DEMO  •  PAPER  •  LIVE",
                17,
                True,
                PURPLE_LIGHT
            )
        )

        mode.add_widget(
            self.label(
                "LIVE TRADING OFF BY DEFAULT",
                11,
                True,
                MUTED
            )
        )

        emergency = self.button(
            "EMERGENCY STOP",
            46
        )

        emergency.color = RED

        mode.add_widget(emergency)

        container.add_widget(mode)
