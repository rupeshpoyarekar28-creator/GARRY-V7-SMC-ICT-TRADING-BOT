
"""GARRY V7 — public market dashboard.
Public market data only. Live orders and Paper Trading are disabled.
"""

from math import cos, sin, pi

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget

from app.state import APPROVED_SYMBOLS, AppState
from data.market_feed import DeltaMarketFeed


# ------------------------- COLOUR THEME -------------------------

BG = (0.012, 0.027, 0.060, 1)
CARD = (0.027, 0.060, 0.105, 1)
CARD2 = (0.045, 0.090, 0.145, 1)
WHITE = (0.91, 0.96, 1.00, 1)
MUTED = (0.56, 0.68, 0.79, 1)
BLUE = (0.10, 0.48, 0.90, 1)
BLUE_LIGHT = (0.30, 0.68, 1.00, 1)
TEAL = (0.08, 0.83, 0.74, 1)
GREEN = (0.18, 0.84, 0.61, 1)
RED = (1.00, 0.35, 0.38, 1)
ORANGE = (1.00, 0.68, 0.25, 1)


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
        if self.width <= 0 or self.height <= 0:
            return

        x, y = self.center
        s = min(self.width, self.height) * 0.72
        x1, x2 = x - s * 0.38, x + s * 0.38
        y1, y2 = y - s * 0.32, y + s * 0.32

        with self.canvas:
            Color(*self.icon_color)

            if self.page_name == "HOME":
                Line(points=[
                    x-s*.48, y, x, y+s*.43,
                    x+s*.48, y, x1, y, x1, y1,
                    x2, y1, x2, y
                ], width=1.5)

            elif self.page_name == "MARKETS":
                Line(points=[x1, y1, x1, y2, x2, y2], width=1.4)
                Line(points=[
                    x-s*.29, y-s*.12,
                    x-s*.08, y+s*.06,
                    x+s*.08, y-s*.02,
                    x+s*.30, y+s*.24
                ], width=1.8)

            elif self.page_name == "TRADES":
                for off, length in (
                    (s*.24, s*.48), (0, s*.62), (-s*.24, s*.48)
                ):
                    Line(points=[
                        x-length/2, y+off,
                        x+length/2, y+off
                    ], width=1.7)

            elif self.page_name == "ANALYSIS":
                Ellipse(
                    pos=(x-s*.34, y-s*.2),
                    size=(s*.53, s*.53)
                )
                Line(points=[
                    x+s*.1, y-s*.13,
                    x+s*.39, y-s*.42
                ], width=2)

            else:
                r = s * 0.28
                Ellipse(pos=(x-r, y-r), size=(2*r, 2*r))
                Ellipse(
                    pos=(x-s*.09, y-s*.09),
                    size=(s*.18, s*.18)
                )
                for i in range(8):
                    a = 2*pi*i/8
                    Line(points=[
                        x+cos(a)*s*.32, y+sin(a)*s*.32,
                        x+cos(a)*s*.43, y+sin(a)*s*.43
                    ], width=1.8)


class NavItem(BoxLayout):
    def __init__(self, page_name, callback, **kwargs):
        super().__init__(**kwargs)
        self.page_name = page_name
        self.callback = callback

    def on_touch_down(self, touch):
        if (
            self.collide_point(*touch.pos)
            and not getattr(touch, "is_mouse_scrolling", False)
            and getattr(touch, "button", None) is None
        ):
            self.callback(self.page_name)
            return True
        return super().on_touch_down(touch)


class DashboardUI(BoxLayout):
    """Dashboard; public data only, no live order submission."""

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

        self.market_snapshots = {}
        self.market_error = ""
        self._market_feed_started = False
        self._retry_pending = False
        self._last_refresh = 0.0
        self._feed_generation = 0
        self.market_feed = None

        self._create_feed()

        with self.canvas.before:
            Color(*BG)
            self.background = RoundedRectangle(
                pos=self.pos, size=self.size
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

    # ------------------------- MARKET FEED -------------------------

    def _create_feed(self):
        try:
            self.market_feed = DeltaMarketFeed()
            self.market_feed.add_callback(self._on_market_snapshot)
            self.market_error = ""
        except Exception as exc:
            self.market_feed = None
            self.market_error = (
                f"Feed initialization failed: {type(exc).__name__}: "
                f"{str(exc)[:160]}"
            )

    def start_market_feed(self, *_):
        if self._market_feed_started:
            return

        try:
            if self.market_feed is None:
                self._create_feed()

            if self.market_feed is None:
                raise RuntimeError("Market feed could not initialize")

            self.market_feed.start()
            self._market_feed_started = True
            self.market_error = "Connecting to Delta public market data..."

        except Exception as exc:
            self._market_feed_started = False
            self.market_error = (
                f"Feed start failed: {type(exc).__name__}: {str(exc)[:160]}"
            )

        self._refresh_market_page()

    def stop_market_feed(self, *_):
        if self.market_feed is not None:
            try:
                self.market_feed.stop()
            except Exception as exc:
                self.market_error = (
                    f"Feed stop failed: {type(exc).__name__}: {str(exc)[:120]}"
                )

        self._market_feed_started = False

    def retry_market_feed(self, *_):
        """Restart feed without blocking the Kivy UI."""
        if self._retry_pending:
            self.market_error = "Retry already in progress..."
            self._refresh_market_page()
            return

        self._retry_pending = True
        self.market_error = "Retry requested — reconnecting..."
        self._refresh_market_page()

        try:
            self.stop_market_feed()
            Clock.schedule_once(self._restart_market_feed, 0.25)
        except Exception as exc:
            self._retry_pending = False
            self.market_error = (
                f"Retry failed: {type(exc).__name__}: {str(exc)[:160]}"
            )
            self._refresh_market_page()

    def _restart_market_feed(self, _dt):
        try:
            old_feed = self.market_feed

            if old_feed is not None:
                try:
                    old_feed.remove_callback(self._on_market_snapshot)
                except Exception:
                    pass

            self.market_feed = None
            self._create_feed()
            self._market_feed_started = False

            if self.market_feed is None:
                raise RuntimeError("Could not initialize a fresh feed")

            self.start_market_feed()

            if self._market_feed_started:
                self.market_error = (
                    "Feed restarted. Waiting for ticker response..."
                )

        except Exception as exc:
            self._market_feed_started = False
            self.market_error = (
                f"Reconnect failed: {type(exc).__name__}: {str(exc)[:160]}"
            )

        finally:
            self._retry_pending = False
            self._refresh_market_page()

    def _on_market_snapshot(self, snapshot):
        # All Kivy widget updates must happen on the UI thread.
        generation = self._feed_generation
        Clock.schedule_once(
            lambda dt, item=snapshot, gen=generation:
                self._apply_snapshot(item, gen),
            0,
        )

    def _apply_snapshot(self, snapshot, generation=None):
        if generation is not None and generation != self._feed_generation:
            return

        symbol = getattr(snapshot, "symbol", None)
        if symbol not in APPROVED_SYMBOLS:
            return

        self.market_snapshots[symbol] = snapshot

        # Preserve the most recently received valid price, even if
        # the connection later becomes stale or temporarily fails.
        price = self._valid_price(getattr(snapshot, "last_price", None))
        if symbol == self.state.symbol:
            if price is not None:
                self.state.price = price

            self.state.connection_status = self._snapshot_status(snapshot)

        error = str(getattr(snapshot, "error", "") or "").strip()
        if error:
            self.market_error = f"{symbol}: {error[:200]}"
        elif self._snapshot_status(snapshot) == "LIVE":
            self.market_error = ""

        now = Clock.get_time()
        if now - self._last_refresh >= 1:
            self._last_refresh = now
            self._refresh_market_page()

    @staticmethod
    def _valid_price(value):
        try:
            number = float(value)
            if number > 0 and number != float("inf") and number == number:
                return number
        except (TypeError, ValueError, OverflowError):
            pass
        return None

    def _snapshot_status(self, snapshot):
        if snapshot is None:
            return "OFFLINE"

        try:
            stale_value = getattr(snapshot, "is_stale", True)
            stale = stale_value() if callable(stale_value) else stale_value
            status = str(getattr(snapshot, "status", "OFFLINE")).upper()
            price = self._valid_price(getattr(snapshot, "last_price", None))

            if stale:
                return "STALE" if price is not None else "OFFLINE"

            if status in ("CONNECTED", "LIVE"):
                return "LIVE"

            if status == "ERROR" and price is not None:
                return "STALE"

            return status

        except Exception:
            return "ERROR"

    def _price(self, symbol):
        """Return the last valid price; status separately indicates freshness."""
        snapshot = self.market_snapshots.get(symbol)
        if snapshot is None:
            return None

        return self._valid_price(getattr(snapshot, "last_price", None))

    def _symbol_error(self, symbol):
        snapshot = self.market_snapshots.get(symbol)
        if snapshot is None:
            return ""

        return str(getattr(snapshot, "error", "") or "").strip()

    def _updated_time(self, symbol):
        snapshot = self.market_snapshots.get(symbol)
        return str(
            getattr(snapshot, "updated_utc", "") or "No successful update"
        )

    def _refresh_market_page(self):
        if self.current_page in ("HOME", "MARKETS", "SETTINGS"):
            self.navigate(self.current_page)

    # ------------------------- UI HELPERS -------------------------

    def _get_scale(self):
        return max(
            0.82,
            min(1.12, (Window.width or dp(390)) / dp(390)),
        )

    def d(self, value):
        return dp(value) * self.scale

    def f(self, value):
        return sp(value) * self.scale

    def _update_background(self, *_):
        self.background.pos = self.pos
        self.background.size = self.size

    def _on_window_size(self, *_):
        if self._resizing:
            return

        new_scale = self._get_scale()
        if abs(new_scale - self.scale) < 0.02:
            return

        self._resizing = True
        try:
            self.scale = new_scale
            self.navigation.height = self.d(68)
            self.navigate(self.current_page)
        finally:
            self._resizing = False

    def label(
        self, text, size=14, bold=False, color=WHITE, align="left"
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
            size=lambda item, value: setattr(
                item, "text_size", (max(0, value[0] - self.d(4)), value[1])
            )
        )
        return widget

    def button(self, text, height=48, accent=False):
        return Button(
            text=text,
            size_hint_y=None,
            height=self.d(height),
            font_size=self.f(13),
            bold=True,
            color=WHITE,
            background_normal="",
            background_down="",
            background_color=BLUE if accent else CARD2,
            border=(0, 0, 0, 0),
        )

    def make_card(self, orientation="horizontal", height=70, padding=14):
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

        box = BoxLayout(
            orientation="vertical",
            size_hint=(1, None),
            padding=(self.d(12), self.d(10), self.d(12), self.d(18)),
            spacing=self.d(10),
        )
        box.bind(minimum_height=box.setter("height"))
        scroll.add_widget(box)
        self.page.add_widget(scroll)
        return box

    def header(self, title, subtitle=""):
        header = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=self.d(68 if subtitle else 48),
            spacing=self.d(2),
        )
        header.add_widget(self.label(title, 23, True, WHITE, "center"))

        if subtitle:
            header.add_widget(self.label(subtitle, 10, True, TEAL, "center"))

        return header

    def show_notice(self, title, message):
        content = BoxLayout(
            orientation="vertical", padding=dp(16), spacing=dp(12)
        )
        msg = Label(
            text=str(message), color=WHITE, halign="center", valign="middle"
        )
        msg.bind(size=lambda widget, size: setattr(widget, "text_size", size))
        content.add_widget(msg)

        close = Button(
            text="OK",
            size_hint_y=None,
            height=dp(44),
            background_normal="",
            background_color=BLUE,
            color=WHITE,
        )
        content.add_widget(close)

        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.85, None),
            height=dp(230),
            auto_dismiss=False,
        )
        close.bind(on_release=popup.dismiss)
        popup.open()

    # ------------------------- NAVIGATION -------------------------

    def build_navigation(self):
        nav = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=self.d(68),
            padding=(self.d(5), self.d(5)),
            spacing=self.d(2),
        )

        with nav.canvas.before:
            Color(*CARD)
            nav.nav_background = RoundedRectangle(
                pos=nav.pos, size=nav.size, radius=[self.d(15)]
            )

        nav.bind(
            pos=lambda _, value: setattr(nav.nav_background, "pos", value),
            size=lambda _, value: setattr(nav.nav_background, "size", value),
        )

        self.nav_buttons = {}
        self.nav_icons = {}
        self.nav_indicators = {}

        for name in ("HOME", "MARKETS", "TRADES", "ANALYSIS", "SETTINGS"):
            item = NavItem(
                page_name=name,
                callback=self.navigate,
                orientation="vertical",
                spacing=self.d(1),
                padding=(self.d(2), self.d(4)),
            )

            with item.canvas.before:
                color = Color(*(BLUE if name == self.current_page else CARD))
                shape = RoundedRectangle(
                    pos=item.pos, size=item.size, radius=[self.d(10)]
                )

            item.bind(
                pos=lambda _, value, s=shape: setattr(s, "pos", value),
                size=lambda _, value, s=shape: setattr(s, "size", value),
            )

            icon = NavIcon(name, size_hint=(1, 0.62))
            label = Label(
                text=name,
                size_hint=(1, 0.38),
                font_size=self.f(8.5),
                bold=True,
                color=TEAL if name == self.current_page else MUTED,
                halign="center",
                valign="middle",
            )

            item.add_widget(icon)
            item.add_widget(label)
            nav.add_widget(item)

            self.nav_buttons[name] = label
            self.nav_icons[name] = icon
            self.nav_indicators[name] = (item, color, shape)

        return nav

    def refresh_navigation(self):
        for name, label in self.nav_buttons.items():
            active = name == self.current_page
            label.color = TEAL if active else MUTED
            self.nav_icons[name].set_color(TEAL if active else MUTED)

            _, color, _ = self.nav_indicators[name]
            color.rgba = (
                (BLUE[0], BLUE[1], BLUE[2], 0.25) if active else CARD
            )

    def navigate(self, page):
        pages = {
            "HOME": self.show_home,
            "MARKETS": self.show_markets,
            "TRADES": self.show_trades,
            "ANALYSIS": self.show_analysis,
            "SETTINGS": self.show_settings,
        }

        if page not in pages:
            page = "HOME"

        self.current_page = page
        pages[page]()
        self.refresh_navigation()

    def change_symbol(self, spinner, value):
        if value not in APPROVED_SYMBOLS:
            spinner.text = self.state.symbol
            return

        self.state.symbol = value
        price = self._price(value)

        if price is not None:
            self.state.price = price

        self.state.connection_status = self._snapshot_status(
            self.market_snapshots.get(value)
        )
        self.show_home()
        self.refresh_navigation()

    # ------------------------- HOME -------------------------

    def show_home(self):
        self.clear_page()
        box = self.scroll_container()
        box.add_widget(self.header("GARRY V7", "SMC / ICT • MARKET DASHBOARD"))

        symbol = self.state.symbol
        snapshot = self.market_snapshots.get(symbol)
        price = self._price(symbol)
        status = self._snapshot_status(snapshot)
        error = self._symbol_error(symbol)

        card = self.make_card(height=78)
        left = BoxLayout(orientation="vertical")
        left.add_widget(self.label("PUBLIC MARKET DATA", 10, True, MUTED))
        left.add_widget(self.label(
            status, 17, True, GREEN if status == "LIVE" else ORANGE
        ))
        card.add_widget(left)
        card.add_widget(self.label(
            "LIVE ORDERS DISABLED", 10, True, BLUE_LIGHT, "right"
        ))
        box.add_widget(card)

        if self.market_error:
            box.add_widget(self.label(self.market_error, 10, False, ORANGE))

        market = self.make_card(orientation="vertical", height=172)
        row = BoxLayout(
            size_hint_y=None, height=self.d(38), spacing=self.d(6)
        )
        row.add_widget(self.label("SELECT MARKET", 11, True, MUTED))

        selector = Spinner(
            text=symbol,
            values=APPROVED_SYMBOLS,
            size_hint_x=None,
            width=self.d(128),
            font_size=self.f(12),
            background_normal="",
            background_color=CARD2,
            color=WHITE,
        )
        selector.bind(text=self.change_symbol)
        row.add_widget(selector)
        market.add_widget(row)

        # Show the last valid received price even when status is STALE.
        market.add_widget(self.label(
            f"{price:,.2f}" if price is not None else "--",
            27, True, WHITE, "center"
        ))
        market.add_widget(self.label(
            "Delta Exchange India • public ticker"
            if price is not None else "Waiting for public market price",
            10, False, TEAL if price is not None else MUTED, "center"
        ))
        market.add_widget(self.label(
            "Updated: " + self._updated_time(symbol),
            8, False, MUTED, "center"
        ))
        if error:
            market.add_widget(self.label(
                "API error: " + error[:180], 9, False, RED, "center"
            ))
        box.add_widget(market)

        scan = self.make_card(orientation="vertical", height=118)
        scan.add_widget(self.label("SMC / ICT SETUP STATUS", 11, True, MUTED))
        scan.add_widget(self.label("NO TRADE", 22, True, TEAL, "center"))
        scan.add_widget(self.label(
            "Strategy signals are not verified in this build.",
            10, False, MUTED, "center"
        ))
        box.add_widget(scan)

        safety = self.make_card(orientation="vertical", height=88)
        safety.add_widget(self.label("SAFETY STATUS", 12, True, BLUE_LIGHT))
        safety.add_widget(self.label(
            "Order placement disabled • Public data only",
            10, False, MUTED, "center"
        ))
        box.add_widget(safety)

    # ------------------------- MARKETS -------------------------

    def show_markets(self):
        self.clear_page()
        box = self.scroll_container()
        box.add_widget(self.header(
            "MARKETS", "DELTA EXCHANGE INDIA • PUBLIC DATA"
        ))

        for symbol in APPROVED_SYMBOLS:
            price = self._price(symbol)
            snapshot = self.market_snapshots.get(symbol)
            status = self._snapshot_status(snapshot)
            error = self._symbol_error(symbol)

            card = self.make_card(height=82)
            left = BoxLayout(orientation="vertical")
            left.add_widget(self.label(symbol, 14, True))
            left.add_widget(self.label(
                status, 9, False, GREEN if status == "LIVE" else ORANGE
            ))
            if error:
                left.add_widget(self.label(
                    "API: " + error[:100], 8, False, RED
                ))

            right = BoxLayout(orientation="vertical")
            right.add_widget(self.label(
                f"{price:,.2f}" if price is not None else "--",
                14, True, GREEN if status == "LIVE" else ORANGE, "right"
            ))
            right.add_widget(self.label(
                self._updated_time(symbol), 8, False, MUTED, "right"
            ))

            card.add_widget(left)
            card.add_widget(right)
            box.add_widget(card)

        box.add_widget(self.label(
            "Public prices only. No exchange orders are sent.",
            10, False, MUTED, "center"
        ))

    # ------------------------- TRADES -------------------------

    def show_trades(self):
        self.clear_page()
        box = self.scroll_container()
        box.add_widget(self.header("TRADES", "ORDER SAFETY"))

        card = self.make_card(orientation="vertical", height=140)
        card.add_widget(self.label(
            "ORDER PLACEMENT DISABLED", 16, True, ORANGE, "center"
        ))
        card.add_widget(self.label(
            "This build does not submit live exchange orders. "
            "Paper Trading is not enabled.",
            11, False, MUTED, "center"
        ))
        box.add_widget(card)

        for name, value in (
            ("LIVE ORDERS", "DISABLED"),
            ("PUBLIC DATA", "NO API KEY REQUIRED"),
            ("EXCHANGE ACCOUNT", "NOT CONNECTED"),
        ):
            item = self.make_card(height=52)
            item.add_widget(self.label(name, 10, True, MUTED))
            item.add_widget(self.label(value, 10, True, WHITE, "right"))
            box.add_widget(item)

    # ------------------------- ANALYSIS -------------------------

    def show_analysis(self):
        self.clear_page()
        box = self.scroll_container()
        box.add_widget(self.header(
            "ANALYSIS", "SMC / ICT MARKET STRUCTURE"
        ))

        for name, value in (
            ("MARKET STRUCTURE", "NOT CALCULATED"),
            ("BOS / CHOCH", "NOT CALCULATED"),
            ("LIQUIDITY SWEEP", "NOT CALCULATED"),
            ("ORDER BLOCK", "NOT CALCULATED"),
            ("FAIR VALUE GAP", "NOT CALCULATED"),
            ("IDM / INDUCEMENT", "NOT CALCULATED"),
            ("SIGNAL", "NO TRADE"),
        ):
            card = self.make_card(orientation="vertical", height=58)
            card.add_widget(self.label(name, 10, True, MUTED))
            card.add_widget(self.label(
                value, 12, True, TEAL if value == "NO TRADE" else WHITE
            ))
            box.add_widget(card)

        box.add_widget(self.label(
            "SMC/ICT signals remain unverified until a strategy engine "
            "is tested against market candles.",
            10, False, ORANGE
        ))

    # ------------------------- SETTINGS -------------------------

    def show_settings(self):
        self.clear_page()
        box = self.scroll_container()
        box.add_widget(self.header("SETTINGS", "PUBLIC DATA • SAFETY"))

        data = self.make_card(orientation="vertical", height=116)
        data.add_widget(self.label(
            "DELTA PUBLIC MARKET DATA", 13, True, BLUE_LIGHT
        ))
        data.add_widget(self.label(
            "Public ticker requests do not need API credentials. "
            "This dashboard does not collect or store private keys.",
            10, False, MUTED
        ))
        data.add_widget(self.label(
            "Feed: " + ("RUNNING" if self._market_feed_started else "STOPPED"),
            11, True, GREEN if self._market_feed_started else ORANGE
        ))
        box.add_widget(data)

        feed = self.make_card(orientation="vertical", height=156)
        feed.add_widget(self.label(
            "MARKET DATA CONNECTION", 13, True, BLUE_LIGHT
        ))
        feed.add_widget(self.label(
            self.market_error or "Public REST ticker feed.",
            10, False, MUTED
        ))

        retry = self.button("RETRY PUBLIC FEED", 48, True)
        retry.bind(on_release=self.retry_market_feed)
        feed.add_widget(retry)
        box.add_widget(feed)

        trading = self.make_card(orientation="vertical", height=110)
        trading.add_widget(self.label(
            "TRADING SAFETY", 13, True, BLUE_LIGHT
        ))
        trading.add_widget(self.label(
            "LIVE ORDER PLACEMENT: DISABLED\n"
            "Fingerprint unlock is not integrated in this file.",
            10, False, ORANGE
        ))
        box.add_widget(trading)

    # Compatibility methods required by main.py.
    def stop_paper(self, *_):
        return None

    def start_paper(self, *_):
        self.show_notice(
            "DISABLED", "Paper Trading is not enabled in this build."
        )

    def emergency_stop(self, *_):
        self.show_notice(
            "LIVE ORDERS DISABLED", "No live exchange orders are enabled."
        )

    def on_parent(self, widget, parent):
        """Compatibility hook; no automatic feed start here."""
        return
