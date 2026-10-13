
"""GARRY V7 — public market dashboard and strategy backtesting UI.

Paper Trading removed.
Backtesting is historical analysis only.
Live order execution is not implemented or enabled here.
"""

import threading
from datetime import datetime, timezone, timedelta

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget

from app.state import APPROVED_SYMBOLS, AppState
from data.market_feed import DeltaMarketFeed


BG = (0.012, 0.027, 0.060, 1)
CARD = (0.027, 0.060, 0.105, 1)
CARD2 = (0.045, 0.090, 0.145, 1)
WHITE = (0.91, 0.96, 1.00, 1)
MUTED = (0.56, 0.68, 0.79, 1)
BLUE = (0.10, 0.48, 0.90, 1)
TEAL = (0.08, 0.83, 0.74, 1)
GREEN = (0.18, 0.84, 0.61, 1)
RED = (1.00, 0.35, 0.38, 1)
ORANGE = (1.00, 0.68, 0.25, 1)


class Card(BoxLayout):
    def __init__(self, **kwargs):
        kwargs.setdefault("padding", dp(12))
        kwargs.setdefault("spacing", dp(8))
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*CARD)
            self.bg = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(14)],
            )

        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *_):
        self.bg.pos = self.pos
        self.bg.size = self.size


class DashboardUI(BoxLayout):
    """Public market dashboard with offline-safe backtesting controls."""

    def __init__(self, state: AppState, **kwargs):
        super().__init__(
            orientation="vertical",
            spacing=0,
            **kwargs,
        )

        self.state = state
        self.current_page = "HOME"
        self.market_snapshots = {}
        self.market_error = ""
        self.market_feed = None
        self._market_feed_started = False
        self._retry_pending = False
        self._feed_generation = 0
        self._last_refresh = 0.0

        self.backtest_running = False
        self.backtest_result = None
        self.backtest_message = "Choose a market and run a historical backtest."
        self.backtest_symbol = self.state.symbol
        self.backtest_timeframe = "5m"
        self.backtest_days = "30"

        self._create_feed()

        with self.canvas.before:
            Color(*BG)
            self.background = RoundedRectangle(
                pos=self.pos,
                size=self.size,
            )

        self.bind(pos=self._update_background, size=self._update_background)

        self.page = BoxLayout(orientation="vertical")
        self.add_widget(self.page)

        self.navigation = self._build_navigation()
        self.add_widget(self.navigation)

        self.show_home()
        Window.bind(size=self._on_window_size)

    # -------------------- BASIC UI --------------------

    def _update_background(self, *_):
        self.background.pos = self.pos
        self.background.size = self.size

    def _on_window_size(self, *_):
        self.navigate(self.current_page)

    def label(self, text, size=14, color=WHITE, bold=False,
              align="left", height=None):
        item = Label(
            text=str(text),
            color=color,
            font_size=sp(size),
            bold=bold,
            halign=align,
            valign="middle",
            size_hint_y=None if height else 1,
            height=dp(height) if height else 0,
        )
        item.bind(
            size=lambda widget, value: setattr(
                widget, "text_size", (max(0, value[0] - dp(6)), value[1])
            )
        )
        return item

    def button(self, text, accent=False, height=46):
        return Button(
            text=text,
            size_hint_y=None,
            height=dp(height),
            color=WHITE,
            bold=True,
            font_size=sp(13),
            background_normal="",
            background_down="",
            background_color=BLUE if accent else CARD2,
            border=(0, 0, 0, 0),
        )

    def card(self, orientation="vertical", height=None):
        return Card(
            orientation=orientation,
            size_hint_y=None if height else 1,
            height=dp(height) if height else 0,
        )

    def scroll_box(self):
        scroll = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(3),
        )
        content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=(dp(12), dp(10), dp(12), dp(18)),
            spacing=dp(10),
        )
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)
        self.page.add_widget(scroll)
        return content

    def header(self, title, subtitle=""):
        result = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(62 if subtitle else 42),
            spacing=dp(2),
        )
        result.add_widget(
            self.label(title, 22, WHITE, True, "center")
        )
        if subtitle:
            result.add_widget(
                self.label(subtitle, 10, TEAL, True, "center")
            )
        return result

    def _build_navigation(self):
        nav = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(62),
            padding=dp(4),
            spacing=dp(3),
        )
        self.nav_buttons = {}

        for name in ("HOME", "MARKETS", "ANALYSIS", "BACKTEST", "SETTINGS"):
            btn = Button(
                text=name,
                font_size=sp(9),
                bold=True,
                color=WHITE,
                background_normal="",
                background_down="",
                background_color=BLUE if name == "HOME" else CARD2,
                border=(0, 0, 0, 0),
            )
            btn.bind(on_release=lambda _btn, page=name: self.navigate(page))
            nav.add_widget(btn)
            self.nav_buttons[name] = btn

        return nav

    def navigate(self, page):
        pages = {
            "HOME": self.show_home,
            "MARKETS": self.show_markets,
            "ANALYSIS": self.show_analysis,
            "BACKTEST": self.show_backtest,
            "SETTINGS": self.show_settings,
        }
        if page not in pages:
            page = "HOME"

        self.current_page = page
        for name, btn in self.nav_buttons.items():
            btn.background_color = BLUE if name == page else CARD2

        pages[page]()

    def _set_page(self, title, subtitle=""):
        self.page.clear_widgets()
        content = self.scroll_box()
        content.add_widget(self.header(title, subtitle))
        return content

    def _show_feed_status(self):
        if self.market_error:
            return self.market_error
        return "Public market feed running" if self._market_feed_started else (
            "Waiting for public market data"
        )

    # -------------------- PUBLIC MARKET FEED --------------------

    def _create_feed(self):
        try:
            self.market_feed = DeltaMarketFeed()
            self.market_feed.add_callback(self._on_market_snapshot)
            self.market_error = ""
        except Exception as exc:
            self.market_feed = None
            self.market_error = f"Feed setup error: {type(exc).__name__}"

    def start_market_feed(self, *_):
        if self._market_feed_started:
            return
        try:
            if self.market_feed is None:
                self._create_feed()
            if self.market_feed is None:
                raise RuntimeError("Feed could not initialize")
            self.market_feed.start()
            self._market_feed_started = True
            self.market_error = "Connecting to Delta public market data..."
        except Exception as exc:
            self._market_feed_started = False
            self.market_error = f"Feed start error: {type(exc).__name__}"
        self._refresh_visible_page()

    def stop_market_feed(self, *_):
        self._feed_generation += 1
        if self.market_feed is not None:
            try:
                self.market_feed.stop()
            except Exception as exc:
                self.market_error = f"Feed stop error: {type(exc).__name__}"
        self._market_feed_started = False

    def retry_market_feed(self, *_):
        if self._retry_pending:
            self.market_error = "Retry already in progress..."
            self._refresh_visible_page()
            return

        self._retry_pending = True
        self.market_error = "Reconnecting to public market data..."
        self._feed_generation += 1
        self._refresh_visible_page()

        try:
            old_feed = self.market_feed
            if old_feed is not None:
                try:
                    old_feed.remove_callback(self._on_market_snapshot)
                    old_feed.stop()
                except Exception:
                    pass

            self.market_feed = None
            self._create_feed()
            self._market_feed_started = False
            if self.market_feed is None:
                raise RuntimeError("Could not create feed")

            self.start_market_feed()
        except Exception as exc:
            self.market_error = f"Retry error: {type(exc).__name__}"
        finally:
            self._retry_pending = False
            self._refresh_visible_page()

    def _on_market_snapshot(self, snapshot):
        generation = self._feed_generation
        Clock.schedule_once(
            lambda _dt, item=snapshot, gen=generation:
                self._apply_snapshot(item, gen),
            0,
        )

    def _apply_snapshot(self, snapshot, generation):
        if generation != self._feed_generation:
            return

        symbol = getattr(snapshot, "symbol", None)
        if symbol not in APPROVED_SYMBOLS:
            return

        self.market_snapshots[symbol] = snapshot
        if symbol == self.state.symbol:
            try:
                price = float(getattr(snapshot, "last_price", 0) or 0)
                if price > 0:
                    self.state.price = price
                self.state.connection_status = self._snapshot_status(snapshot)
            except (TypeError, ValueError, AttributeError):
                self.state.connection_status = "ERROR"

        error = getattr(snapshot, "error", "")
        if error:
            self.market_error = f"{symbol}: {error}"

        now = Clock.get_time()
        if now - self._last_refresh >= 1:
            self._last_refresh = now
            self._refresh_visible_page()

    def _snapshot_status(self, snapshot):
        if snapshot is None:
            return "OFFLINE"
        try:
            stale = getattr(snapshot, "is_stale", True)
            stale = stale() if callable(stale) else stale
            status = str(getattr(snapshot, "status", "OFFLINE")).upper()
            if stale:
                return "STALE" if getattr(snapshot, "last_price", None) else "OFFLINE"
            return "LIVE" if status in ("CONNECTED", "LIVE") else status
        except Exception:
            return "ERROR"

    def _price(self, symbol):
        snapshot = self.market_snapshots.get(symbol)
        if self._snapshot_status(snapshot) != "LIVE":
            return None
        try:
            value = float(getattr(snapshot, "last_price", 0) or 0)
            return value if value > 0 else None
        except (TypeError, ValueError, OverflowError):
            return None

    def _updated_time(self, symbol):
        snapshot = self.market_snapshots.get(symbol)
        return getattr(snapshot, "updated_utc", "") or "No successful update"

    def _refresh_visible_page(self):
        if self.current_page in ("HOME", "MARKETS", "SETTINGS"):
            self.navigate(self.current_page)

    # -------------------- HOME --------------------

    def show_home(self):
        box = self._set_page("GARRY V7", "SMC / ICT • PUBLIC MARKET DASHBOARD")

        status = self._snapshot_status(self.market_snapshots.get(self.state.symbol))
        price = self._price(self.state.symbol)

        status_card = self.card(height=76)
        status_card.add_widget(self.label("PUBLIC MARKET CONNECTION", 11, MUTED, True))
        status_card.add_widget(
            self.label(status, 18, GREEN if status == "LIVE" else ORANGE, True)
        )
        box.add_widget(status_card)

        if self.market_error:
            box.add_widget(self.label(self.market_error, 10, ORANGE))

        market = self.card(height=170)
        market.add_widget(self.label("SELECT MARKET", 11, MUTED, True))
        selector = Spinner(
            text=self.state.symbol,
            values=APPROVED_SYMBOLS,
            size_hint_y=None,
            height=dp(42),
            background_normal="",
            background_color=CARD2,
            color=WHITE,
        )
        selector.bind(text=self._change_symbol)
        market.add_widget(selector)
        market.add_widget(
            self.label(
                f"{price:,.2f}" if price is not None else "--",
                27, WHITE, True, "center",
            )
        )
        market.add_widget(
            self.label(
                "Delta Exchange India • public ticker",
                10, TEAL, False, "center",
            )
        )
        box.add_widget(market)

        bt = self.button("OPEN STRATEGY BACKTEST", True)
        bt.bind(on_release=lambda *_: self.navigate("BACKTEST"))
        box.add_widget(bt)

        safety = self.card(height=76)
        safety.add_widget(self.label("TRADING STATUS", 12, TEAL, True))
        safety.add_widget(self.label(
            "Backtesting only • No exchange orders sent",
            10, MUTED,
        ))
        box.add_widget(safety)

    def _change_symbol(self, _spinner, value):
        if value not in APPROVED_SYMBOLS:
            return
        self.state.symbol = value
        self.state.connection_status = self._snapshot_status(
            self.market_snapshots.get(value)
        )
        self.navigate("HOME")

    # -------------------- MARKETS --------------------

    def show_markets(self):
        box = self._set_page("MARKETS", "DELTA EXCHANGE INDIA • PUBLIC DATA")

        for symbol in APPROVED_SYMBOLS:
            price = self._price(symbol)
            status = self._snapshot_status(self.market_snapshots.get(symbol))
            row = self.card(orientation="horizontal", height=66)
            left = BoxLayout(orientation="vertical")
            left.add_widget(self.label(symbol, 13, WHITE, True))
            left.add_widget(self.label(status, 9, GREEN if status == "LIVE" else ORANGE))
            right = BoxLayout(orientation="vertical")
            right.add_widget(self.label(
                f"{price:,.2f}" if price is not None else "--",
                14, WHITE, True, "right",
            ))
            right.add_widget(self.label(
                str(self._updated_time(symbol)), 8, MUTED, False, "right",
            ))
            row.add_widget(left)
            row.add_widget(right)
            box.add_widget(row)

        retry = self.button("RETRY PUBLIC MARKET FEED", True)
        retry.bind(on_release=self.retry_market_feed)
        box.add_widget(retry)

    # -------------------- ANALYSIS --------------------

    def show_analysis(self):
        box = self._set_page("ANALYSIS", "SMC / ICT • CANDLE ANALYSIS")

        for name, value in (
            ("MARKET STRUCTURE", "NOT CALCULATED"),
            ("BOS / CHOCH", "NOT CALCULATED"),
            ("LIQUIDITY SWEEP", "NOT CALCULATED"),
            ("ORDER BLOCK", "NOT CALCULATED"),
            ("FAIR VALUE GAP", "NOT CALCULATED"),
            ("IDM / INDUCEMENT", "NOT CALCULATED"),
        ):
            item = self.card(height=54)
            item.add_widget(self.label(name, 10, MUTED, True))
            item.add_widget(self.label(value, 12, WHITE, True))
            box.add_widget(item)

        box.add_widget(self.label(
            "Live signals are not verified by this screen. Use backtesting "
            "to evaluate a strategy on historical candles.",
            10, ORANGE,
        ))

    # -------------------- STRATEGY BACKTEST --------------------

    def show_backtest(self):
        box = self._set_page(
            "STRATEGY BACKTEST",
            "HISTORICAL CANDLES • NO LIVE ORDERS",
        )

        settings = self.card(height=220)
        settings.add_widget(self.label("BACKTEST SETTINGS", 13, TEAL, True))

        settings.add_widget(self.label("Market", 10, MUTED, True, height=22))
        symbol = Spinner(
            text=self.backtest_symbol,
            values=APPROVED_SYMBOLS,
            size_hint_y=None,
            height=dp(38),
            background_normal="",
            background_color=CARD2,
            color=WHITE,
        )
        symbol.bind(text=lambda _w, value: setattr(self, "backtest_symbol", value))
        settings.add_widget(symbol)

        settings.add_widget(self.label("Timeframe", 10, MUTED, True, height=22))
        timeframe = Spinner(
            text=self.backtest_timeframe,
            values=("1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"),
            size_hint_y=None,
            height=dp(38),
            background_normal="",
            background_color=CARD2,
            color=WHITE,
        )
        timeframe.bind(
            text=lambda _w, value: setattr(self, "backtest_timeframe", value)
        )
        settings.add_widget(timeframe)

        settings.add_widget(self.label("History window", 10, MUTED, True, height=22))
        days = Spinner(
            text=self.backtest_days,
            values=("7", "14", "30", "60", "90"),
            size_hint_y=None,
            height=dp(38),
            background_normal="",
            background_color=CARD2,
            color=WHITE,
        )
        days.bind(text=lambda _w, value: setattr(self, "backtest_days", value))
        settings.add_widget(days)
        box.add_widget(settings)

        run_button = self.button(
            "RUN HISTORICAL BACKTEST" if not self.backtest_running else "BACKTEST RUNNING...",
            True,
        )
        run_button.disabled = self.backtest_running
        run_button.bind(on_release=self.run_strategy_backtest)
        box.add_widget(run_button)

        result = self.card(height=250)
        result.add_widget(self.label("BACKTEST RESULTS", 13, TEAL, True))
        result.add_widget(self.label(
            self.backtest_message, 11, WHITE,
        ))

        if isinstance(self.backtest_result, dict):
            for key in (
                "symbol", "timeframe", "candles", "total_trades",
                "winning_trades", "losing_trades", "win_rate",
                "net_pnl", "profit_factor", "max_drawdown",
            ):
                if key in self.backtest_result:
                    result.add_widget(self.label(
                        f"{key.replace('_', ' ').title()}: "
                        f"{self.backtest_result[key]}",
                        10, MUTED,
                    ))
        box.add_widget(result)

        box.add_widget(self.label(
            "Backtest results are historical simulations, not guaranteed "
            "future performance. Fees/slippage must be included by the engine.",
            9, ORANGE,
        ))

    def run_strategy_backtest(self, *_):
        if self.backtest_running:
            return

        self.backtest_running = True
        self.backtest_result = None
        self.backtest_message = "Downloading historical candles and running strategy..."
        self.navigate("BACKTEST")

        symbol = self.backtest_symbol
        timeframe = self.backtest_timeframe
        days = int(self.backtest_days)

        def worker():
            try:
                # This module is supplied as File 2.
                from strategy.backtest import run_backtest

                result = run_backtest(
                    symbol=symbol,
                    resolution=timeframe,
                    days=days,
                )
                if not isinstance(result, dict):
                    raise TypeError("Backtest engine returned an invalid result")
                Clock.schedule_once(
                    lambda _dt, data=result: self._backtest_complete(data, None),
                    0,
                )
            except Exception as exc:
                message = f"{type(exc).__name__}: {str(exc)[:220]}"
                Clock.schedule_once(
                    lambda _dt, error=message: self._backtest_complete(None, error),
                    0,
                )

        threading.Thread(
            target=worker,
            name="GarryStrategyBacktest",
            daemon=True,
        ).start()

    def _backtest_complete(self, result, error):
        self.backtest_running = False
        if error:
            self.backtest_result = None
            self.backtest_message = "Backtest failed: " + error
        else:
            self.backtest_result = result
            self.backtest_message = "Backtest completed. Review metrics below."
        self.navigate("BACKTEST")

    # -------------------- SETTINGS --------------------

    def show_settings(self):
        box = self._set_page("SETTINGS", "PUBLIC DATA • BACKTESTING")

        feed = self.card(height=150)
        feed.add_widget(self.label("MARKET DATA CONNECTION", 13, TEAL, True))
        feed.add_widget(self.label(self._show_feed_status(), 10, MUTED))
        retry = self.button("RETRY PUBLIC FEED", True)
        retry.bind(on_release=self.retry_market_feed)
        feed.add_widget(retry)
        box.add_widget(feed)

        safety = self.card(height=112)
        safety.add_widget(self.label("EXECUTION SAFETY", 13, TEAL, True))
        safety.add_widget(self.label(
            "Paper Trading: REMOVED\nLive Orders: NOT IMPLEMENTED / DISABLED",
            11, ORANGE,
        ))
        box.add_widget(safety)

    # Compatibility methods retained for main.py.
    def stop_paper(self, *_):
        return None

    def start_paper(self, *_):
        return None

    def emergency_stop(self, *_):
        self.stop_market_feed()
