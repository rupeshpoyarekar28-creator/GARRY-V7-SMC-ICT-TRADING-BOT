"""
GARRY V7 SMC ICT TRADING BOT

Clean Android application entry point.

This file intentionally contains no dependency on the old
GARRY V8 project or any V8-specific modules.
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label


class GarryV7App(App):
    """Main application for GARRY V7 SMC ICT TRADING BOT."""

    def build(self):
        self.title = "GARRY V7 SMC ICT TRADING BOT"

        root = BoxLayout(
            orientation="vertical",
            padding=20,
            spacing=15,
        )

        title = Label(
            text="GARRY V7 SMC ICT TRADING BOT",
            font_size="24sp",
            bold=True,
            size_hint_y=None,
            height=60,
        )

        status = Label(
            text="DEMO MODE\nConnection: READY",
            font_size="18sp",
            halign="center",
            valign="middle",
        )

        root.add_widget(title)
        root.add_widget(status)

        return root


if __name__ == "__main__":
    GarryV7App().run()
