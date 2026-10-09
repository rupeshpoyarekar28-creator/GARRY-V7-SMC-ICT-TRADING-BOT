
"""
GARRY V7 SMC ICT TRADING BOT

Login-gated Android dashboard entry point.
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

        # Dashboard is created but remains hidden until login succeeds.
        self.root_layout = LoginScreen(
            on_login=self.open_dashboard
        )

        return self.root_layout

    def open_dashboard(self):
        self.root_layout.clear_widgets()
        self.root_layout.add_widget(self.dashboard)


if __name__ == "__main__":
    GarryV7App().run()
