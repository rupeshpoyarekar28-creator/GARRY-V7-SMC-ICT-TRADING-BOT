
"""
GARRY V7 SMC ICT TRADING BOT
Dashboard + PAPER session integration.
LIVE trading is intentionally disabled.
"""

from math import cos, sin, pi

from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget

from app.state import APPROVED_SYMBOLS, AppState
from app.trading_session import TradingSession


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


class NavIcon(Widget):
    """Draw vector icons for the bottom navigation."""

    def __init__(self, page_name, **kwargs):
        self.page_name = page_name
        self.icon_color = MUTED
        super().__init__(**kwargs)
        self.bind(pos=self.redraw, size=self.redraw)

    def set_color(self, color):
        self.icon_color = color
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()

        w, h = self.width, self.height
        if w <= 0 or h <= 0:
            return

        cx, cy = self.center
        s = min(w, h) * 0.72
        x1, x2 = cx - s * 0.38, cx + s * 0.38
        y1, y2 = cy - s * 0.32, cy + s * 0.32

        with self.canvas:
            Color(*self.icon_color)

            if self.page_name == "HOME":
                Line(points=[
                    cx - s * .48, cy, cx, cy + s * .43,
                    cx + s * .48, cy
                ], width=1.5, cap="round", joint="round")
                Line(points=[
                    x1, cy, x1, y1, x2, y1, x2, cy
                ], width=1.5, cap="round", joint="round")
                Line(points=[
                    cx - s * .1, y1, cx - s * .1, cy,
                    cx + s * .1, cy, cx + s * .1, y1
                ], width=1.3)

            elif self.page_name == "MARKETS":
                Line(points=[x1, y1, x1, y2, x2, y2], width=1.4)
                Line(points=[
                    cx - s * .29, cy - s * .12,
                    cx - s * .08, cy + s * .06,
                    cx + s * .08, cy - s * .02,
                    cx + s * .30, cy + s * .24
                ], width=1.8, cap="round", joint="round")

            elif self.page_name == "TRADES":
                for offset, length in [
                    (s * .24, s * .48),
                    (0, s * .62),
                    (-s * .24, s * .48),
                ]:
                    Line(points=[
                        cx - length / 2, cy + offset,
                        cx + length / 2, cy + offset
                    ], width=1.7, cap="round")
                    Ellipse(
                        pos=(cx - length / 2 - s * .09,
                             cy + offset - s * .035),
                        size=(s * .07, s * .07),
                    )

            elif self.page_name == "ANALYSIS":
                Ellipse(
                    pos=(cx - s * .34, cy - s * .20),
                    size=(s * .53, s * .53),
                )
                Line(points=[
                    cx + s * .10, cy - s * .13,
                    cx + s * .39, cy - s * .42
                ], width=2, cap="round")

            elif self.page_name == "SETTINGS":
                radius = s * .28
                Ellipse(
                    pos=(cx - radius, cy - radius),
                    size=(radius * 2, radius * 2),
                )
                Ellipse(
                    pos=(cx - s * .09, cy - s * .09),
                    size=(s * .18, s * .18),
                )
                for i in range(8):
                    angle = 2 * pi * i / 8
                    Line(points=[
                        cx + cos(angle) * s * .32,
                        cy + sin(angle) * s * .32,
                        cx + cos(angle) * s * .43,
                        cy + sin(angle) * s * .43,
                    ], width=1.8, cap="round")


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

        self.paper_status = "PAPER STOPPED"
        self.paper_result = {}
        self.paper_error = ""
        self.mode = "PAPER"

        # Session uses public market data and virtual paper orders only.
        self.paper_session = TradingSession(
            on_update=self._on_paper_update,
            on_error=self._on_paper_error,
        )

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
    # PAPER SESSION CALLBACKS AND CONTROLS
    # ---------------------------------------------------------

    def _on_paper_update(self, result):
        self.paper_result = result or {}
        self.paper_status = str(
            self.paper_result.get("status", "PAPER UPDATE")
        )
        self.paper_error = ""

        # UI state only; this does not enable exchange orders.
        self.state.trading_enabled = self.paper_session.running

        if self.current_page == "HOME":
            self.show_home()
            self.refresh_navigation()
        elif self.current_page == "TRADES":
            self.show_trades()

    def _on_paper_error(self, message):
        self.paper_error = str(message)
        self.paper_status = "PAPER ERROR"

        if self.current_page == "HOME":
            self.show_home()

    def start_paper(self, *_):
        if self.mode != "PAPER":
            self.show_notice(
                "MODE DISABLED",
                "Only PAPER mode is available in this build.",
            )
            return

        try:
            self.paper_session.start_paper(self.state.symbol)
            self.paper_status = "PAPER STARTING"
            self.paper_error = ""
            self.state.trading_enabled = True
            self.show_home()
        except Exception as exc:
            self.paper_error = str(exc)
            self.paper_status = "PAPER START FAILED"
            self.show_notice("PAPER START ERROR", str(exc))

    def stop_paper(self, *_):
        self.paper_session.stop()
        self.state.trading_enabled = False
        self.paper_status = "PAPER STOPPED"
        self.show_home()

    def select_mode(self, spinner, value):
        if value == "LIVE (DISABLED)":
            self.mode = "PAPER"
            spinner.text = "PAPER"
            self.show_notice(
                "LIVE DISABLED",
                "LIVE order execution is not implemented or enabled. "
                "PAPER mode remains selected.",
            )
            return

        self.mode = "PAPER"

    def stop_bot(self, *_):
        self.stop_paper()

    def save_api_notice(self, *_):
        self.show_notice(
            "API SETUP",
            "API credentials are not being saved. "
            "Secure credential storage is not integrated yet.",
        )

    def test_api_notice(self, *_):
        self.show_notice(
            "API CONNECTION",
            "Private API connection has not been tested. "
            "This build uses public market data for PAPER analysis.",
        )

    def emergency_stop(self, *_):
        self.stop_paper()
        self.show_notice(
            "PAPER STOPPED",
            "The app's PAPER session has been stopped. "
            "This is not a VPS or exchange kill switch.",
        )

    # ---------------------------------------------------------
    # GENERAL HELPERS
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

    def _get_scale(self):
        width = Window.width or dp(390)
        return max(0.82, min(1.12, width / dp(390)))

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
        self.navigation.height = self.d(68)
        self.navigation.padding = self.d(5)
        self.navigation.spacing = self.d(2)
        self.navigate(self.current_page)
        self._resizing = False

    def _update_background(self, *_):
        self.background.pos = self.pos
        self.background.size = self.size

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
            setattr(
                instance,
                "text_size",
                (max(0, value[0] - self.d(4)), value[1]),
            )
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
                self.d(12), self.d(10),
                self.d(12), self.d(18),
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
        box.add_widget(
            self.label(title, 24, True, WHITE, "center")
        )

        if subtitle:
            box.add_widget(
                self.label(
                    subtitle, 11, True, PURPLE_LIGHT, "center"
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
            height=self.d(68),
            padding=(self.d(5), self.d(5)),
            spacing=self.d(2),
        )

        with navigation.canvas.before:
            Color(*CARD)
            navigation.nav_background = RoundedRectangle(
                pos=navigation.pos,
                size=navigation.size,
                radius=[self.d(15)],
            )

        navigation.bind(
            pos=lambda instance, value: setattr(
                navigation.nav_background, "pos", value
            ),
            size=lambda instance, value: setattr(
                navigation.nav_background, "size", value
            ),
        )

        self.nav_buttons = {}
        self.nav_icons = {}
        self.nav_indicators = {}

        for page_name in [
            "HOME", "MARKETS", "TRADES", "ANALYSIS", "SETTINGS"
        ]:
            item = BoxLayout(
                orientation="vertical",
                spacing=self.d(1),
                padding=(self.d(2), self.d(4)),
            )

            with item.canvas.before:
                indicator_color = Color(
                    *(PURPLE if page_name == self.current_page else CARD)
                )
                indicator = RoundedRectangle(
                    pos=item.pos,
                    size=item.size,
                    radius=[self.d(10)],
                )

            item.bind(
                pos=lambda instance, value, shape=indicator:
                setattr(shape, "pos", value),
                size=lambda instance, value, shape=indicator:
                setattr(shape, "size", value),
            )

            icon_widget = NavIcon(
                page_name,
                size_hint=(1, 0.62),
            )

            label_widget = Label(
                text=page_name,
                size_hint=(1, 0.38),
                font_size=self.f(8.5),
                bold=True,
                color=(
                    PURPLE_LIGHT
                    if page_name == self.current_page
                    else MUTED
                ),
                halign="center",
                valign="middle",
            )

            item.add_widget(icon_widget)
            item.add_widget(label_widget)
            item.bind(
                on_touch_down=lambda instance, touch, p=page_name:
                self._nav_touch(instance, touch, p)
            )
            navigation.add_widget(item)

            self.nav_buttons[page_name] = label_widget
            self.nav_icons[page_name] = icon_widget
            self.nav_indicators[page_name] = (
                item, indicator_color, indicator
            )

        return navigation

    def _nav_touch(self, instance, touch, page_name):
        if instance.collide_point(*touch.pos):
            if touch.is_mouse_scrolling:
                return False
            if touch.button is None:
                self.navigate(page_name)
                return True
        return False

    def refresh_navigation(self):
        for page_name, label_widget in self.nav_buttons.items():
            active = page_name == self.current_page
            label_widget.color = PURPLE_LIGHT if active else MUTED
            label_widget.font_size = self.f(8.5)
            self.nav_icons[page_name].set_color(
                PURPLE_LIGHT if active else MUTED
            )

            _, indicator_color, _ = self.nav_indicators[page_name]
            indicator_color.rgba = (
                (PURPLE[0], PURPLE[1], PURPLE[2], 0.28)
                if active else CARD
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
            self.header("GARRY V7", "SMC / ICT TRADING BOT")
        )

        system = self.make_card(height=90)
        status_box = BoxLayout(orientation="vertical")
        status_box.add_widget(
            self.label("PAPER ENGINE STATUS", 10, False, MUTED)
        )

        status_color = (
            GREEN if self.paper_session.running
            else ORANGE if not self.paper_error
            else RED
        )
        status_text = (
            "PAPER RUNNING"
            if self.paper_session.running
            else self.paper_status
        )
        status_box.add_widget(
            self.label(status_text, 15, True, status_color)
        )
        system.add_widget(status_box)
        system.add_widget(
            self.label("LIVE ORDERS: DISABLED", 10, True, MUTED, "right")
        )
        container.add_widget(system)

        if self.paper_error:
            error_card = self.make_card(
                orientation="vertical",
                height=76,
            )
            error_card.add_widget(
                self.label("PAPER ERROR", 11, True, RED)
            )
            error_card.add_widget(
                self.label(self.paper_error, 10, False, WHITE)
            )
            container.add_widget(error_card)

        market = self.make_card(
            orientation="vertical",
            height=160,
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

        result = self.paper_result
        price = result.get("price")
        price_text = f"{float(price):,.2f}" if price is not None else "--"

        market.add_widget(
            self.label(price_text, 25, True, WHITE, "center")
        )
        market.add_widget(
            self.label(
                "Latest analysis price; not a live ticker feed",
                10, False, MUTED, "center"
            )
        )
        container.add_widget(market)

        signal = self.make_card(
            orientation="vertical",
            height=110,
        )
        signal.add_widget(
            self.label("PAPER ANALYSIS", 11, True, MUTED)
        )
        signal.add_widget(
            self.label(
                result.get("signal", "WAITING"),
                22, True, PURPLE_LIGHT, "center"
            )
        )
        signal.add_widget(
            self.label(
                result.get("reason", "Start PAPER to analyse public candles."),
                10, False, MUTED, "center"
            )
        )
        container.add_widget(signal)

        controls = self.make_card(
            orientation="horizontal",
            height=56,
            padding=8,
        )
        start_button = self.button("START PAPER", 42, True)
        start_button.disabled = self.paper_session.running
        start_button.bind(on_release=self.start_paper)
        controls.add_widget(start_button)

        stop_button = self.button("STOP PAPER", 42)
        stop_button.disabled = not self.paper_session.running
        stop_button.bind(on_release=self.stop_paper)
        controls.add_widget(stop_button)
        container.add_widget(controls)

        container.add_widget(
            self.label(
                "PAPER ONLY • NO EXCHANGE ORDERS",
                10, True, ORANGE, "center"
            )
        )

    def change_symbol(self, spinner, value):
        if value not in APPROVED_SYMBOLS:
            return

        if self.paper_session.running:
            self.show_notice(
                "STOP PAPER FIRST",
                "Stop the PAPER session before changing the symbol.",
            )
            spinner.text = self.state.symbol
            return

        self.state.symbol = value
        try:
            self.paper_session.change_symbol(value)
        except (ValueError, RuntimeError):
            pass

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
                self.label(
                    "PUBLIC DATA NOT LOADED",
                    10, False, MUTED, "right"
                )
            )
            container.add_widget(card)

    # ---------------------------------------------------------
    # TRADES
    # ---------------------------------------------------------

    def _paper_summary(self):
        engine = self.paper_session.engine
        if engine is None:
            return None

        trader = getattr(engine, "trader", None)
        if trader is None:
            return None

        try:
            return trader.summary()
        except Exception:
            return None

    def show_trades(self):
        self.clear_page()
        container = self.scroll_container()
        container.add_widget(
            self.header("TRADES", "TRADE HISTORY & PERFORMANCE")
        )

        summary = self._paper_summary() or {
            "total_trades": 0,
            "closed_trades": 0,
            "wins": 0,
            "losses": 0,
            "realized_pnl": 0.0,
        }

        total = int(summary.get("total_trades", 0))
        closed = int(summary.get("closed_trades", 0))
        wins = int(summary.get("wins", 0))
        losses = int(summary.get("losses", 0))
        pnl = float(summary.get("realized_pnl", 0.0))
        win_rate = f"{(wins / closed) * 100:.1f}%" if closed else "--"

        statistics = self.make_card(
            orientation="vertical",
            height=218,
            padding=16,
        )
        statistics.spacing = self.d(6)

        for name, value in [
            ("TOTAL TRADES", str(total)),
            ("WINNING TRADES", str(wins)),
            ("LOSING TRADES", str(losses)),
            ("WIN RATE", win_rate),
            ("NET P&L", f"₹{pnl:,.2f}"),
        ]:
            row = BoxLayout(
                orientation="horizontal",
                size_hint=(1, None),
                height=self.d(32),
                spacing=self.d(8),
            )
            label = self.label(name, 11, False, MUTED, "left")
            label.size_hint_x = 0.72
            value_color = GREEN if name == "NET P&L" and pnl >= 0 else (
                RED if name == "NET P&L" else WHITE
            )
            result = self.label(value, 12, True, value_color, "right")
            result.size_hint_x = 0.28
            row.add_widget(label)
            row.add_widget(result)
            statistics.add_widget(row)

        container.add_widget(statistics)

        if total == 0:
            container.add_widget(
                self.label(
                    "NO PAPER TRADES YET",
                    13, True, MUTED, "center"
                )
            )
        else:
            container.add_widget(
                self.label(
                    "PAPER RESULTS ONLY • NOT REAL ACCOUNT P&L",
                    10, True, ORANGE, "center"
                )
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

        result = self.paper_result
        reason = result.get("reason", "Start PAPER to run analysis.")
        signal = result.get("signal", "WAITING")

        for item, value in [
            ("MARKET STRUCTURE", "Analysis pending"),
            ("BOS / CHOCH", "Analysis pending"),
            ("LIQUIDITY SWEEP", "Analysis pending"),
            ("ORDER BLOCK", "Analysis pending"),
            ("FVG", "Analysis pending"),
            ("IDM", "Analysis pending"),
            ("SIGNAL", signal),
            ("REASON", reason),
        ]:
            card = self.make_card(
                orientation="vertical",
                height=62,
            )
            card.add_widget(self.label(item, 11, True, MUTED))
            card.add_widget(self.label(value, 10, False, WHITE))
            container.add_widget(card)

        container.add_widget(
            self.label(
                "Detailed SMC/ICT components are not yet individually "
                "mapped to these rows.",
                10, False, ORANGE
            )
        )

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
            height=258,
        )
        api.add_widget(self.label("DELTA API", 15, True))
        api.add_widget(
            self.label(
                "Private API credentials are not integrated",
                10, False, MUTED
            )
        )

        key = TextInput(
            hint_text="API KEY (not saved)",
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
            hint_text="API SECRET (not saved)",
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
            height=200,
        )
        mode.add_widget(self.label("TRADING MODE", 13, True))

        mode_selector = Spinner(
            text="PAPER",
            values=("PAPER", "LIVE (DISABLED)"),
            size_hint_y=None,
            height=self.d(44),
            font_size=self.f(13),
            background_normal="",
            background_color=CARD2,
            color=WHITE,
        )
        mode_selector.bind(text=self.select_mode)
        mode.add_widget(mode_selector)

        mode.add_widget(
            self.label(
                "LIVE TRADING DISABLED",
                10, True, ORANGE
            )
        )

        start_button = self.button("START PAPER", 44, True)
        start_button.bind(on_release=self.start_paper)
        mode.add_widget(start_button)

        stop_button = self.button("STOP PAPER", 44)
        stop_button.bind(on_release=self.stop_paper)
        mode.add_widget(stop_button)

        emergency = self.button("EMERGENCY STOP", 44)
        emergency.color = RED
        emergency.bind(on_release=self.emergency_stop)
        mode.add_widget(emergency)
        container.add_widget(mode)
