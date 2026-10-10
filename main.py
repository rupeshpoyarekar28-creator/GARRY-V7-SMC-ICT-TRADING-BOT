"""
GARRY V7 SMC ICT TRADING BOT

Login-gated Android dashboard entry point.
Public market feed starts only after successful login.
LIVE exchange orders remain disabled.
"""
from kivy.app import App

from app.state import create_default_state
from app.ui import DashboardUI
from app.login import LoginScreen


class GarryV7App(App):
    """GARRY V7 application."""

    def build(self):
        self.title = "GARRY V7 SMC ICT TRADING BOT"
        self.state = create_default_state()
        self.dashboard = DashboardUI(state=self.state)

        # Dashboard remains hidden until login succeeds.
        self.root_layout = LoginScreen(on_login=self.open_dashboard)
        return self.root_layout

    def open_dashboard(self):
        self.root_layout.clear_widgets()
        self.root_layout.add_widget(self.dashboard)

        # Start public market data only after login.
        try:
            self.dashboard.start_market_feed()
        except Exception as exc:
            # Keep the dashboard usable if the feed cannot start.
            self.dashboard.market_error = str(exc)
            if self.dashboard.current_page in ("HOME", "MARKETS"):
                self.dashboard._refresh_market_page()

    def on_stop(self):
        # Stop background data threads when the app exits.
        try:
            self.dashboard.stop_market_feed()
        except Exception:
            pass
        try:
            self.dashboard.stop_paper()
        except Exception:
            pass


if __name__ == "__main__":
    GarryV7App().run()
