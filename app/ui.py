
"""
GARRY V7 SMC ICT TRADING BOT
Responsive Dashboard UI.
Existing pages and approved symbols preserved.
"""

from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup

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

    def __init__(self, scale=1.0, **kwargs):
        self.scale = scale
        kwargs.setdefault("padding", dp(14) * scale)
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*CARD)
            self.bg = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(16) * scale],
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
            **kwargs,
        )

        self.state = state
        self.current_page = "HOME"
        self._resizing = False
        self.scale = self._get_scale()

        with self.canvas.before:
            Color(*BG)
            self.background = RoundedRectangle(
                pos=self.pos,
                size=self.size,
            )

        self.bind(
            pos=self._update_background,
            size=self._update_background,
        )

        self.page = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
        )
        self.add_widget(self.page)

        self.navigation = self.build_navigation()
        self.add_widget(self.navigation)

        self.show_home()
        Window.bind(size=self._on_window_size)

    # ---------------------------------------------------------
    # BUTTON ACTIONS
    # ---------------------------------------------------------

    def show_notice(self, title, message):
        content = BoxLayout(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(12),
        )

        message_label = Label(
            text=message,
            color=WHITE,
            halign="center",
            valign="middle",
        )
        message_label.bind(
            size=lambda instance, value:
            setattr(instance, "text_size", value)
        )
        content.add_widget(message_label)

        close_button = Button(
            text="OK",
            size_hint_y=None,
            height=dp(44),
            background_normal="",
            background_color=PURPLE,
            color=WHITE,
        )
        content.add_widget(close_button)

        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.85, None),
            height=dp(230),
            auto_dismiss=False,
        )
        close_button.bind(on_release=popup.dismiss)
        popup.open()

    def stop_bot(self, *_):
        self.state.trading_enabled = False
        self.show_notice(
            "BOT STATUS",
            "Dashboard trading flag is OFF.\n\n"
            "No live trading engine is connected yet. "
            "This does not stop an external or VPS process.",
        )

    def save_api_notice(self, *_):
        self.show_notice(
            "API SETUP",
            "API credentials have NOT been saved.\n\n"
            "Secure backend integration is required first.",
        )

    def test_api_notice(self, *_):
        self.show_notice(
            "API CONNECTION",
            "API connection has NOT been tested.\n\n"
            "Delta Exchange integration is not connected yet.",
        )

    def emergency_stop(self, *_):
        self.state.trading_enabled = False
        self.show_notice(
            "EMERGENCY STOP",
            "Dashboard trading flag is OFF.\n\n"
            "This is not a real exchange or VPS kill switch yet.",
        )

    # ---------------------------------------------------------
    # RESPONSIVE HELPERS
    # ---------------------------------------------------------

    def _get_scale(self):
        width = Window.width or dp(390)
        base_width = dp(390)
        return max(0.82, min(1.12, width / base_width))

    def d(self, value):
        return dp(value) * self.scale

    def f(self, value):
        return sp(value) * self.scale

    def _on_window_size(self, *_):
        if self._resizing:
            return

        new_scale = self._get_scale()
        if abs(new_scale - self.scale) < 0.02:
            return

        self._resizing = True
        self.scale = new_scale

        self.navigation.height = self.d(64)
        self.navigation.padding = self.d(5)
        self.navigation.spacing = self.d(3)

        self.navigate(self.current_page)
        self._resizing = False

    def _update_background(self, *_):
        self.background.pos = self.pos
        self.background.size = self.size

    # ---------------------------------------------------------
    # UI HELPERS
    # ---------------------------------------------------------

    def label(
        self,
        text,
        size=14,
        bold=False,
        color=WHITE,
        align="left",
    ):
        widget = Label(
            text=str(text),
            font_size=self.f(size),
            bold=bold,
            color=color,
            halign=align,
            valign="middle",
            shorten=False,
        )
        widget.bind(
            size=lambda instance, value:
            setattr(instance, "text_size", (
                max(0, value[0] - self.d(4)),
                value[1],
            ))
        )
        return widget

    def button(self, text, height=48, accent=False):
        return Button(
            text=text,
            size_hint_y=None,
            height=self.d(height),
            font_size=self.f(14),
            bold=True,
            color=WHITE,
            background_normal="",
            background_down="",
            background_color=PURPLE if accent else CARD2,
            border=(0, 0, 0, 0),
        )

    def make_card(
        self,
        orientation="horizontal",
        height=70,
        padding=14,
    ):
        return Card(
            scale=self.scale,
            orientation=orientation,
            size_hint_y=None,
            height=self.d(height),
            padding=self.d(padding),
            spacing=self.d(8),
        )

    def clear_page(self):
        self.page.clear_widgets()

    def scroll_container(self):
        scroll = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=self.d(3),
            scroll_type=["content", "bars"],
        )

        container = BoxLayout(
            orientation="vertical",
            size_hint=(1, None),
            padding=(
                self.d(12),
                self.d(10),
                self.d(12),
                self.d(18),
            ),
            spacing=self.d(10),
        )

        container.bind(
            minimum_height=container.setter("height")
        )
        scroll.add_widget(container)
        self.page.add_widget(scroll)
        return container

    def header(self, title, subtitle=""):
        box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=self.d(68 if subtitle else 48),
            spacing=self.d(2),
        )

        box.add_widget(self.label(title, 24, True))

        if subtitle:
            box.add_widget(
                self.label(subtitle, 11, True, PURPLE_LIGHT)
            )

        return box

    # ---------------------------------------------------------
    # BOTTOM NAVIGATION
    # ---------------------------------------------------------

    def build_navigation(self):
        navigation = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=self.d(64),
            padding=self.d(5),
            spacing=self.d(3),
        )

        self.nav_buttons = {}

        pages = [
            ("HOME", "⌂\nHome"),
            ("MARKETS", "◈\nMarkets"),
            ("TRADES", "▣\nTrades"),
            ("ANALYSIS", "⌁\nAnalysis"),
            ("SETTINGS", "⚙\nSettings"),
        ]

        for page_name, text in pages:
            button = Button(
                text=text,
                font_size=self.f(10),
                color=PURPLE_LIGHT if page_name == self.current_page else MUTED,
                background_normal="",
                background_down="",
                background_color=BG,
                border=(0, 0, 0, 0),
            )
            button.bind(
                on_release=lambda _, p=page_name: self.navigate(p)
            )
            navigation.add_widget(button)
            self.nav_buttons[page_name] = button

        return navigation

    def refresh_navigation(self):
        for page_name, button in self.nav_buttons.items():
            button.color = (
                PURPLE_LIGHT
                if page_name == self.current_page
                else MUTED
            )
            button.font_size = self.f(10)

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
            self.header("GARRY V7", "SMC / ICT TRADING BOT")
        )

        system = self.make_card(height=82)
        status_box = BoxLayout(orientation="vertical")
        status_box.add_widget(self.label("SYSTEM STATUS", 10, False, MUTED))
        status_box.add_widget(
            self.label("NOT CONNECTED", 17, True, ORANGE)
        )
        system.add_widget(status_box)
        system.add_widget(
            self.label("●  ENGINE READY", 11, True, GREEN, "right")
        )
        container.add_widget(system)

        market = self.make_card(
            orientation="vertical",
            height=245,
        )

        top_row = BoxLayout(
            size_hint_y=None,
            height=self.d(40),
            spacing=self.d(6),
        )
        top_row.add_widget(self.label("MARKET", 12, True, MUTED))

        selector = Spinner(
            text=self.state.symbol,
            values=APPROVED_SYMBOLS,
            size_hint_x=None,
            width=self.d(122),
            font_size=self.f(12),
            background_normal="",
            background_color=CARD2,
            color=WHITE,
        )
        selector.bind(text=self.change_symbol)
        top_row.add_widget(selector)
        market.add_widget(top_row)

        market.add_widget(
            self.label("LIVE DATA PENDING", 25, True, WHITE, "center")
        )
        market.add_widget(
            self.label("Delta Exchange India", 12, False, MUTED, "center")
        )

        stats = GridLayout(
            cols=3,
            spacing=self.d(6),
            size_hint_y=None,
            height=self.d(72),
        )

        for name in ["BID", "ASK", "24H"]:
            mini = self.make_card(
                orientation="vertical",
                height=72,
                padding=6,
            )
            mini.add_widget(self.label(name, 9, False, MUTED))
            mini.add_widget(self.label("--", 14, True))
            stats.add_widget(mini)

        market.add_widget(stats)
        container.add_widget(market)

        signal = self.make_card(
            orientation="vertical",
            height=138,
        )
        signal.add_widget(self.label("CURRENT SIGNAL", 11, True, MUTED))
        signal.add_widget(self.label("WAITING", 25, True, WHITE, "center"))
        signal.add_widget(
            self.label(
                "Waiting for valid SMC / ICT confirmation",
                11,
                False,
                MUTED,
                "center",
            )
        )
        container.add_widget(signal)

        levels = self.make_card(
            orientation="vertical",
            height=170,
        )
        levels.add_widget(self.label("TRADE LEVELS", 12, True, MUTED))

        for name in ["ENTRY", "STOP LOSS", "TAKE PROFIT", "RISK", "R:R"]:
            row = BoxLayout(
                size_hint_y=None,
                height=self.d(26),
            )
            row.add_widget(self.label(name, 11, False, MUTED))
            row.add_widget(self.label("--", 11, True, WHITE, "right"))
            levels.add_widget(row)

        container.add_widget(levels)

        stop = self.button("STOP BOT", 48)
        stop.color = RED
        stop.bind(on_release=self.stop_bot)
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
            self.header("MARKETS", "DELTA EXCHANGE INDIA")
        )

        for symbol in APPROVED_SYMBOLS:
            card = self.make_card(height=66)
            card.add_widget(self.label(symbol, 15, True))
            card.add_widget(
                self.label("LIVE DATA PENDING", 10, False, MUTED, "right")
            )
            container.add_widget(card)

    # ---------------------------------------------------------
    # TRADES
    # ---------------------------------------------------------

    def show_trades(self):
        self.clear_page()
        container = self.scroll_container()
        container.add_widget(
            self.header("TRADES", "TRADE HISTORY & PERFORMANCE")
        )

        statistics = self.make_card(
            orientation="vertical",
            height=184,
        )

        for name, value in [
            ("TOTAL TRADES", "0"),
            ("WINNING TRADES", "0"),
            ("LOSING TRADES", "0"),
            ("WIN RATE", "--"),
            ("NET P&L", "₹0.00"),
        ]:
            row = BoxLayout(
                size_hint_y=None,
                height=self.d(30),
            )
            row.add_widget(self.label(name, 11, False, MUTED))
            row.add_widget(self.label(value, 12, True, WHITE, "right"))
            statistics.add_widget(row)

        container.add_widget(statistics)
        container.add_widget(
            self.label("NO TRADES YET", 13, True, MUTED, "center")
        )

    # ---------------------------------------------------------
    # ANALYSIS
    # ---------------------------------------------------------

    def show_analysis(self):
        self.clear_page()
        container = self.scroll_container()
        container.add_widget(
            self.header("ANALYSIS", "SMC / ICT MARKET STRUCTURE")
        )

        analysis_items = [
            "MARKET STRUCTURE",
            "BOS / CHOCH",
            "LIQUIDITY SWEEP",
            "ORDER BLOCK",
            "FVG",
            "IDM",
            "DISPLACEMENT",
            "PREMIUM / DISCOUNT",
        ]

        for item in analysis_items:
            card = self.make_card(height=56)
            card.add_widget(self.label(item, 11, False, MUTED))
            card.add_widget(self.label("WAITING", 11, True, WHITE, "right"))
            container.add_widget(card)

    # ---------------------------------------------------------
    # SETTINGS
    # ---------------------------------------------------------

    def show_settings(self):
        self.clear_page()
        container = self.scroll_container()
        container.add_widget(
            self.header("SETTINGS", "GARRY V7 CONFIGURATION")
        )

        api = self.make_card(
            orientation="vertical",
            height=278,
        )

        api.add_widget(self.label("DELTA API", 15, True))
        api.add_widget(
            self.label("Trading-only credentials", 10, False, MUTED)
        )

        key = TextInput(
            hint_text="API KEY",
            multiline=False,
            size_hint_y=None,
            height=self.d(46),
            font_size=self.f(13),
            background_normal="",
            background_active="",
            background_color=CARD2,
            foreground_color=WHITE,
            hint_text_color=MUTED,
        )

        secret = TextInput(
            hint_text="API SECRET",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=self.d(46),
            font_size=self.f(13),
            background_normal="",
            background_active="",
            background_color=CARD2,
            foreground_color=WHITE,
            hint_text_color=MUTED,
        )

        api.add_widget(key)
        api.add_widget(secret)
        api.add_widget(
            self.label(
                "Never store API secrets in source code or logs.",
                9,
                False,
                MUTED,
            )
        )

        buttons = BoxLayout(
            size_hint_y=None,
            height=self.d(44),
            spacing=self.d(8),
        )

        save_button = self.button("SAVE", 44, True)
        save_button.bind(on_release=self.save_api_notice)
        buttons.add_widget(save_button)

        test_button = self.button("TEST", 44)
        test_button.bind(on_release=self.test_api_notice)
        buttons.add_widget(test_button)

        api.add_widget(buttons)
        container.add_widget(api)

        mode = self.make_card(
            orientation="vertical",
            height=158,
        )
        mode.add_widget(self.label("TRADING MODE", 13, True))
        mode.add_widget(
            self.label("DEMO  •  PAPER  •  LIVE", 15, True, PURPLE_LIGHT)
        )
        mode.add_widget(
            self.label("LIVE TRADING OFF BY DEFAULT", 10, True, MUTED)
        )

        emergency = self.button("EMERGENCY STOP", 44)
        emergency.color = RED
        emergency.bind(on_release=self.emergency_stop)
        mode.add_widget(emergency)
        container.add_widget(mode)
