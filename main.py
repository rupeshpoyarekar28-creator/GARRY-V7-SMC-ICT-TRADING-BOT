
"""
GARRY V7 SMC ICT TRADING BOT
Startup diagnostics and bounded recovery.

Paper Trading is virtual only.
Live exchange orders are disabled.
"""

import logging
import os
import re
import threading
import traceback
from datetime import datetime, timezone

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView

from app.login import LoginScreen
from app.state import create_default_state


APP_NAME = "GARRY V7 SMC ICT TRADING BOT"
BG = (0.025, 0.04, 0.09, 1)
CARD = (0.075, 0.10, 0.17, 1)
BLUE = (0.0, 0.55, 0.78, 1)
WHITE = (0.92, 0.96, 1, 1)
MUTED = (0.68, 0.76, 0.86, 1)
RED = (1.0, 0.38, 0.38, 1)
GREEN = (0.20, 0.85, 0.60, 1)


def _sanitize(text):
    """Remove common secret-shaped values from diagnostic text."""
    text = str(text)
    patterns = [
        (
            r"(?i)(password|api[_ -]?secret|api[_ -]?key|"
            r"access[_ -]?token|refresh[_ -]?token|authorization)"
            r"(\s*[:=]\s*)[^\s,;]+",
            r"\1\2[REDACTED]",
        ),
        (
            r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+",
            r"\1[REDACTED]",
        ),
    ]
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text[:12000]


class StartupDiagnosticManager:
    """Record startup stages, exceptions and recovery attempts."""

    def __init__(self, log_path):
        self.log_path = log_path
        self.lock = threading.RLock()
        self.stage = "APP_CREATED"
        self.ready = False
        self.last_error = None
        self.last_component = None
        self.last_traceback = None
        self.attempts = {}
        self.report = []

        self.logger = logging.getLogger("garry_v7.startup")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        if not self.logger.handlers:
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                handler = logging.FileHandler(
                    log_path, encoding="utf-8"
                )
                handler.setFormatter(logging.Formatter(
                    "%(asctime)sZ %(levelname)s %(message)s"
                ))
            except Exception:
                handler = logging.StreamHandler()

            self.logger.addHandler(handler)

    def record(self, stage, component, message, level="INFO"):
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "timestamp": timestamp,
            "stage": str(stage),
            "component": str(component),
            "message": _sanitize(message),
            "level": level,
        }

        with self.lock:
            self.stage = str(stage)
            self.report.append(entry)
            self.report = self.report[-200:]

        line = (
            f"stage={entry['stage']} "
            f"component={entry['component']} "
            f"message={entry['message']}"
        )

        if level == "ERROR":
            self.logger.error(line)
        elif level == "WARNING":
            self.logger.warning(line)
        else:
            self.logger.info(line)

    def capture_exception(self, stage, component, exc):
        trace = _sanitize(traceback.format_exc())

        with self.lock:
            self.last_error = (
                f"{type(exc).__name__}: {_sanitize(exc)}"
            )
            self.last_component = str(component)
            self.last_traceback = trace
            self.ready = False

        self.record(
            stage,
            component,
            f"{type(exc).__name__}: {exc}\n{trace}",
            "ERROR",
        )

    def recover_failed_component(self, component, error):
        with self.lock:
            count = self.attempts.get(component, 0) + 1
            self.attempts[component] = count

        self.record(
            "RECOVERY",
            component,
            f"attempt={count}; error={error}; "
            "automatic retry is not assumed successful",
            "WARNING",
        )
        return count

    def mark_ready(self):
        with self.lock:
            self.ready = True
            self.last_error = None
            self.last_component = None
            self.last_traceback = None

        self.record(
            "DASHBOARD_READY",
            "DashboardUI",
            "Dashboard constructed and attached to root.",
        )

    def get_startup_diagnostic_report(self):
        with self.lock:
            return {
                "stage": self.stage,
                "dashboard_ready": self.ready,
                "last_error": self.last_error,
                "failed_component": self.last_component,
                "traceback": self.last_traceback,
                "attempts": dict(self.attempts),
                "events": list(self.report),
                "log_path": self.log_path,
            }


def run_startup_diagnostics(manager):
    """Return the latest diagnostic report without exposing credentials."""
    return manager.get_startup_diagnostic_report()


class StartupErrorScreen(BoxLayout):
    """Show the actual sanitized failure and allow a guarded retry."""

    def __init__(self, app, message, details="", **kwargs):
        super().__init__(
            orientation="vertical",
            padding=18,
            spacing=12,
            **kwargs,
        )

        self.app = app

        with self.canvas.before:
            Color(*BG)
            self.bg_rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
            )

        self.bind(pos=self._update_bg, size=self._update_bg)

        heading = Label(
            text="DASHBOARD INITIALIZATION FAILED",
            size_hint_y=None,
            height=42,
            color=RED,
            bold=True,
        )
        self.add_widget(heading)

        self.message = Label(
            text=_sanitize(message),
            size_hint_y=None,
            height=90,
            color=WHITE,
            halign="center",
            valign="middle",
        )
        self.message.bind(
            size=lambda w, s: setattr(w, "text_size", s)
        )
        self.add_widget(self.message)

        scroll = ScrollView(do_scroll_x=False)
        self.details_label = Label(
            text=_sanitize(details) or "No traceback available.",
            size_hint_y=None,
            color=MUTED,
            halign="left",
            valign="top",
        )
        self.details_label.bind(
            width=lambda w, width: setattr(w, "text_size", (width, None)),
            texture_size=lambda w, size: setattr(w, "height", size[1] + 12),
        )
        scroll.add_widget(self.details_label)
        self.add_widget(scroll)

        self.retry_button = Button(
            text="RETRY FAILED INITIALIZATION",
            size_hint_y=None,
            height=50,
            background_normal="",
            background_color=BLUE,
            color=WHITE,
        )
        self.retry_button.bind(on_release=self._retry)
        self.add_widget(self.retry_button)

        self.log_label = Label(
            text=f"Diagnostic log: {app.diagnostics.log_path}",
            size_hint_y=None,
            height=44,
            color=MUTED,
            font_size="10sp",
            halign="center",
        )
        self.add_widget(self.log_label)

    def _update_bg(self, *_):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def _retry(self, *_):
        self.retry_button.disabled = True
        self.retry_button.text = "RETRYING..."
        self.app.retry_dashboard()


class GarryV7App(App):
    def build(self):
        self.title = APP_NAME

        log_path = os.path.join(
            self.user_data_dir,
            "garry_startup.log",
        )
        self.diagnostics = StartupDiagnosticManager(log_path)

        self.state = None
        self.dashboard = None
        self.login_screen = None

        self._stopped = False
        self._initializing = False
        self._generation = 0
        self._last_failed_stage = None
        self._retry_count = 0
        self._max_retry_count = 3

        self.diagnostics.record(
            "APP_BUILD",
            "GarryV7App",
            "Starting login UI.",
        )

        try:
            self.login_screen = LoginScreen(
                on_login=self.open_dashboard
            )
            return self.login_screen
        except Exception as exc:
            self.diagnostics.capture_exception(
                "LOGIN_UI_BUILD",
                "LoginScreen.__init__",
                exc,
            )
            return StartupErrorScreen(
                self,
                self.diagnostics.last_error,
                self.diagnostics.last_traceback,
            )

    def open_dashboard(self, *_):
        """Schedule dashboard creation after successful local login."""
        if self._stopped or self._initializing:
            self.diagnostics.record(
                "DUPLICATE_INITIALIZATION",
                "open_dashboard",
                "Duplicate request ignored.",
                "WARNING",
            )
            return

        self._initializing = True
        self._generation += 1
        generation = self._generation
        self._retry_count = 0

        self.diagnostics.record(
            "LOGIN_SUCCESS",
            "LoginScreen.submit",
            "Login callback received; preparing dashboard.",
        )

        Clock.schedule_once(
            lambda dt: self.initialize_dashboard_safely(generation),
            0,
        )

    def initialize_dashboard_safely(self, generation=None):
        """Construct and display the core dashboard, without network waits."""
        if generation is None:
            generation = self._generation

        if self._stopped or generation != self._generation:
            self._initializing = False
            return

        if self.dashboard is not None:
            self._attach_dashboard(generation)
            return

        try:
            self.diagnostics.record(
                "STATE_INITIALIZATION",
                "create_default_state",
                "Creating local application state.",
            )
            if self.state is None:
                self.state = create_default_state()

            self.diagnostics.record(
                "DASHBOARD_IMPORT",
                "app.ui.DashboardUI",
                "Importing dashboard class.",
            )
            from app.ui import DashboardUI

            self.diagnostics.record(
                "DASHBOARD_CONSTRUCTION",
                "DashboardUI.__init__",
                "Constructing dashboard widgets and local session objects.",
            )
            dashboard = DashboardUI(state=self.state)

            self.diagnostics.record(
                "DASHBOARD_ATTACH",
                "root_layout",
                "Attaching dashboard to application root.",
            )
            self.dashboard = dashboard
            self._attach_dashboard(generation)

        except Exception as exc:
            self._last_failed_stage = self.diagnostics.stage
            self.diagnostics.capture_exception(
                self.diagnostics.stage,
                self.diagnostics.last_component or "Dashboard initialization",
                exc,
            )
            self._initializing = False
            self._show_error_screen()

    def _attach_dashboard(self, generation):
        if self._stopped or generation != self._generation:
            self._initializing = False
            return

        try:
            if self.root is None:
                raise RuntimeError("Kivy root widget is unavailable.")

            if self.dashboard is None:
                raise RuntimeError("Dashboard object was not created.")

            self.root.clear_widgets()
            self.root.add_widget(self.dashboard)

            if self.dashboard.parent is not self.root:
                raise RuntimeError(
                    "Dashboard health check failed: widget is not attached."
                )

            self._initializing = False
            self.diagnostics.mark_ready()

            # Market data is optional. Start it only after the dashboard
            # is visible; errors must not undo successful UI initialization.
            Clock.schedule_once(
                lambda dt: self._start_market_feed(generation),
                0.25,
            )

        except Exception as exc:
            self._last_failed_stage = "DASHBOARD_ATTACH"
            self.diagnostics.capture_exception(
                "DASHBOARD_ATTACH",
                "GarryV7App._attach_dashboard",
                exc,
            )
            self._initializing = False
            self._show_error_screen()

    def _start_market_feed(self, generation):
        if (
            self._stopped
            or generation != self._generation
            or self.dashboard is None
        ):
            return

        try:
            self.diagnostics.record(
                "OPTIONAL_MARKET_FEED",
                "DashboardUI.start_market_feed",
                "Starting public market feed after UI attachment.",
            )
            self.dashboard.start_market_feed()
            self.diagnostics.record(
                "OPTIONAL_MARKET_FEED",
                "DashboardUI.start_market_feed",
                "Feed start call returned; this does not imply live data received.",
            )
        except Exception as exc:
            self.diagnostics.capture_exception(
                "OPTIONAL_MARKET_FEED",
                "DashboardUI.start_market_feed",
                exc,
            )

            try:
                self.dashboard.market_error = (
                    f"Market feed unavailable: "
                    f"{type(exc).__name__}: {_sanitize(exc)}"
                )
                Clock.schedule_once(
                    lambda dt: self.dashboard.show_home(),
                    0,
                )
            except Exception:
                self.diagnostics.record(
                    "OPTIONAL_MARKET_FEED",
                    "Error display",
                    "Unable to refresh feed error display.",
                    "ERROR",
                )

    def _show_error_screen(self):
        if self._stopped or self.root is None:
            return

        report = run_startup_diagnostics(self.diagnostics)
        message = (
            f"Stage: {report['stage']}\n"
            f"Component: {report['failed_component'] or 'Unknown'}\n"
            f"Error: {report['last_error'] or 'No exception captured'}"
        )

        try:
            self.root.clear_widgets()
            self.root.add_widget(
                StartupErrorScreen(
                    self,
                    message,
                    report["traceback"] or "",
                )
            )
        except Exception:
            self.diagnostics.logger.exception(
                "Could not render diagnostic screen"
            )

    def retry_dashboard(self):
        """Guard retry attempts and avoid duplicate concurrent initialization."""
        if self._stopped or self._initializing:
            return

        if self.dashboard is not None:
            # The dashboard object was created. Retry attachment rather than
            # constructing another feed/session manager.
            self._initializing = True
            self._generation += 1
            generation = self._generation
            Clock.schedule_once(
                lambda dt: self._attach_dashboard(generation),
                0,
            )
            return

        if self._retry_count >= self._max_retry_count:
            self.diagnostics.record(
                "RETRY_LIMIT",
                "retry_dashboard",
                "Maximum retry count reached; inspect diagnostic log.",
                "ERROR",
            )
            self._show_error_screen()
            return

        self._retry_count += 1
        self._initializing = True
        self._generation += 1
        generation = self._generation

        self.diagnostics.recover_failed_component(
            self._last_failed_stage or "Dashboard initialization",
            self.diagnostics.last_error or "Unknown error",
        )

        # A short scheduled retry prevents recursive UI callbacks.
        Clock.schedule_once(
            lambda dt: self.initialize_dashboard_safely(generation),
            min(0.5 * self._retry_count, 2.0),
        )

    def on_stop(self):
        self._stopped = True
        self._generation += 1

        if self.dashboard is not None:
            try:
                self.dashboard.stop_market_feed()
            except Exception as exc:
                self.diagnostics.capture_exception(
                    "SHUTDOWN_MARKET_FEED",
                    "DashboardUI.stop_market_feed",
                    exc,
                )

            try:
                self.dashboard.stop_paper()
            except Exception as exc:
                self.diagnostics.capture_exception(
                    "SHUTDOWN_PAPER",
                    "DashboardUI.stop_paper",
                    exc,
                )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    GarryV7App().run()
