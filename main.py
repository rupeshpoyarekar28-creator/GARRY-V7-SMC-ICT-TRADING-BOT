
"""
GARRY V7 SMC ICT TRADING BOT
Startup-safe Android application entry point.

Paper Trading is virtual only.
Live exchange orders remain disabled.
"""

import logging
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

from app.state import create_default_state
from app.login import LoginScreen


logger = logging.getLogger("garry_v7.startup")


class StartupScreen(BoxLayout):
    """Visible recovery screen for dashboard initialization failures."""

    def __init__(self, retry_callback, **kwargs):
        super().__init__(
            orientation="vertical",
            padding=24,
            spacing=16,
            **kwargs,
        )

        self.retry_callback = retry_callback

        with self.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(0.025, 0.04, 0.09, 1)
            self._background = Rectangle(
                pos=self.pos,
                size=self.size,
            )

        self.bind(pos=self._update_bg, size=self._update_bg)

        self.message = Label(
            text="Dashboard could not initialize.",
            color=(0.9, 0.95, 1, 1),
            halign="center",
            valign="middle",
        )
        self.message.bind(
            size=lambda widget, size: setattr(
                widget, "text_size", size
            )
        )
        self.add_widget(self.message)

        retry = Button(
            text="RETRY",
            size_hint_y=None,
            height=52,
            background_normal="",
            background_color=(0.0, 0.55, 0.75, 1),
        )
        retry.bind(on_release=self._retry)
        self.add_widget(retry)

    def _update_bg(self, *_):
        self._background.pos = self.pos
        self._background.size = self.size

    def _retry(self, *_):
        self.retry_callback()


class GarryV7App(App):
    """GARRY V7 startup and login lifecycle."""

    def build(self):
        self.title = "GARRY V7 SMC ICT TRADING BOT"

        self.state = None
        self.dashboard = None
        self.root_layout = None

        self._opening_dashboard = False
        self._stopped = False
        self._startup_generation = 0

        # Keep build() lightweight: return login without constructing
        # market feeds, trading engines, or making network requests.
        self.root_layout = LoginScreen(
            on_login=self.open_dashboard
        )
        return self.root_layout

    def open_dashboard(self, *_):
        """Initialize dashboard after login, without blocking the UI."""
        if self._stopped or self._opening_dashboard:
            return

        self._opening_dashboard = True
        self._startup_generation += 1
        generation = self._startup_generation

        # Give Kivy a chance to render the login screen before
        # constructing the heavier dashboard modules.
        Clock.schedule_once(
            lambda _dt: self._initialize_dashboard(generation),
            0.1,
        )

    def _initialize_dashboard(self, generation):
        if self._stopped or generation != self._startup_generation:
            self._opening_dashboard = False
            return

        try:
            from app.ui import DashboardUI

            if self.state is None:
                self.state = create_default_state()

            dashboard = DashboardUI(state=self.state)

            if self._stopped or generation != self._startup_generation:
                try:
                    dashboard.stop_market_feed()
                except Exception:
                    pass
                try:
                    dashboard.stop_paper()
                except Exception:
                    pass
                self._opening_dashboard = False
                return

            self.dashboard = dashboard
            self.root_layout.clear_widgets()
            self.root_layout.add_widget(dashboard)

            # Mark initialization complete only after the dashboard
            # has actually been attached to the root widget.
            self._opening_dashboard = False

            # Start public market data after the UI is visible.
            Clock.schedule_once(
                lambda _dt: self._start_market_feed(generation),
                0.5,
            )

        except Exception:
            logger.exception("Dashboard initialization failed")
            self._opening_dashboard = False
            self._show_startup_error(
                "Dashboard initialization failed. "
                "Check the application startup log and retry."
            )

    def _start_market_feed(self, generation):
        """Start public market data separately from UI initialization."""
        if (
            self._stopped
            or generation != self._startup_generation
            or self.dashboard is None
        ):
            return

        try:
            # start_market_feed should start background workers and
            # return promptly; it must not perform blocking HTTP calls.
            self.dashboard.start_market_feed()
        except Exception:
            logger.exception("Market feed startup failed")
            try:
                self.dashboard.market_error = (
                    "Market feed unavailable. Retrying is possible."
                )
                self.dashboard._refresh_market_page()
            except Exception:
                logger.exception("Market feed error UI update failed")

    def _show_startup_error(self, message):
        if self._stopped:
            return

        try:
            screen = StartupScreen(
                retry_callback=self._retry_dashboard,
            )
            screen.message.text = message
            self.root_layout.clear_widgets()
            self.root_layout.add_widget(screen)
        except Exception:
            logger.exception("Unable to show startup recovery screen")

    def _retry_dashboard(self):
        if self._stopped or self._opening_dashboard:
            return

        self._opening_dashboard = True
        self._startup_generation += 1
        generation = self._startup_generation

        Clock.schedule_once(
            lambda _dt: self._initialize_dashboard(generation),
            0.1,
        )

    def on_stop(self):
        self._stopped = True
        self._startup_generation += 1

        dashboard = self.dashboard
        if dashboard is None:
            return

        try:
            dashboard.stop_market_feed()
        except Exception:
            logger.exception("Market feed shutdown failed")

        try:
            dashboard.stop_paper()
        except Exception:
            logger.exception("Paper session shutdown failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    GarryV7App().run()
