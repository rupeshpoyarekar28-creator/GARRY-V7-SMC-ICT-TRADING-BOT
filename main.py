"""
GARRY V7 SMC ICT TRADING BOT

Clean Android application entry point.

This file connects the application state with the
GARRY V7 dashboard UI.

No dependency on the old GARRY V8 project is used.
Real trading execution is disabled.
"""

from kivy.app import App

from app.state import create_default_state
from app.ui import DashboardUI


class GarryV7App(App):
    """Main application for GARRY V7 SMC ICT TRADING BOT."""

    def build(self):
        self.title = "GARRY V7 SMC ICT TRADING BOT"

        state = create_default_state()

        return DashboardUI(state=state)


if __name__ == "__main__":
    GarryV7App().run()
