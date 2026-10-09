
"""
GARRY V7 - Responsive Login / First-time Account Setup

Responsive layout only.
Authentication and password validation are preserved.
This is a local prototype, not production-grade authentication.
"""

import hashlib
import hmac
import json
import os
import secrets

from kivy.app import App
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget


BG = (0.025, 0.023, 0.035, 1)
CARD = (0.075, 0.070, 0.095, 1)
CARD2 = (0.105, 0.095, 0.135, 1)
WHITE = (0.96, 0.95, 1, 1)
MUTED = (0.58, 0.56, 0.65, 1)
PURPLE = (0.48, 0.28, 0.95, 1)
RED = (0.95, 0.25, 0.32, 1)

ITERATIONS = 300_000


def derive_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        ITERATIONS,
    ).hex()


class LoginScreen(BoxLayout):

    def __init__(self, on_login, **kwargs):
        super().__init__(
            orientation="vertical",
            padding=dp(0),
            spacing=0,
            **kwargs,
        )

        self.on_login = on_login
        self.account_file = os.path.join(
            App.get_running_app().user_data_dir,
            "local_account.json",
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

        # Scrollable layout for short displays and landscape mode.
        self.scroll = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(3),
            scroll_type=["content", "bars"],
        )
        self.add_widget(self.scroll)

        self.content = BoxLayout(
            orientation="vertical",
            size_hint=(1, None),
            spacing=dp(14),
            padding=(dp(20), dp(16), dp(20), dp(20)),
        )
        self.content.bind(
            minimum_height=self.content.setter("height")
        )
        self.scroll.add_widget(self.content)

        self.content.add_widget(Widget(size_hint_y=None, height=dp(12)))

        self.content.add_widget(self._label(
            "[b]GARRY V7[/b]",
            30,
            WHITE,
            markup=True,
            height=dp(48),
        ))

        self.content.add_widget(self._label(
            "SMC / ICT TRADING BOT",
            13,
            PURPLE,
            height=dp(28),
        ))

        self.content.add_widget(Widget(size_hint_y=None, height=dp(8)))

        self.heading = self._label(
            "CREATE YOUR APP LOGIN",
            17,
            WHITE,
            bold=True,
            height=dp(42),
        )
        self.content.add_widget(self.heading)

        self.app_id = TextInput(
            hint_text="Choose App ID",
            multiline=False,
            size_hint=(1, None),
            height=dp(52),
            font_size=sp(16),
            background_normal="",
            background_active="",
            background_color=CARD2,
            foreground_color=WHITE,
            hint_text_color=MUTED,
            cursor_color=PURPLE,
            padding=(dp(12), dp(14)),
        )
        self.password = TextInput(
            hint_text="Choose password (12+ characters)",
            password=True,
            multiline=False,
            size_hint=(1, None),
            height=dp(52),
            font_size=sp(16),
            background_normal="",
            background_active="",
            background_color=CARD2,
            foreground_color=WHITE,
            hint_text_color=MUTED,
            cursor_color=PURPLE,
            padding=(dp(12), dp(14)),
        )

        self.content.add_widget(self.app_id)
        self.content.add_widget(self.password)

        self.message = self._label(
            "First launch: create your account on this device.",
            12,
            MUTED,
            height=dp(58),
        )
        self.content.add_widget(self.message)

        self.action = Button(
            text="CREATE ACCOUNT",
            size_hint=(1, None),
            height=dp(52),
            font_size=sp(15),
            background_normal="",
            background_down="",
            background_color=PURPLE,
            color=WHITE,
            bold=True,
        )
        self.action.bind(on_release=self.submit)
        self.content.add_widget(self.action)

        self.content.add_widget(Widget(size_hint_y=None, height=dp(12)))

        # Adapt margins and vertical spacing to the available width.
        self.bind(size=self._adapt_layout)
        self._adapt_layout()
        self._refresh_mode()

    def _label(
        self,
        text,
        size,
        color,
        bold=False,
        markup=False,
        height=dp(40),
    ):
        label = Label(
            text=text,
            font_size=sp(size),
            color=color,
            bold=bold,
            markup=markup,
            halign="center",
            valign="middle",
            size_hint=(1, None),
            height=height,
            shorten=False,
        )
        label.bind(
            size=lambda instance, value:
            setattr(instance, "text_size", (
                max(0, value[0] - dp(8)),
                value[1],
            ))
        )
        return label

    def _update_background(self, *_):
        self.background.pos = self.pos
        self.background.size = self.size

    def _adapt_layout(self, *_):
        width = self.width or dp(360)

        # Keep side margins comfortable on small and large phones.
        margin = max(dp(14), min(dp(32), width * 0.065))
        self.content.padding = (
            margin,
            dp(16),
            margin,
            dp(20),
        )

        self.content.spacing = max(
            dp(9),
            min(dp(16), width * 0.035),
        )

    def _load_account(self):
        try:
            with open(self.account_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _refresh_mode(self):
        exists = self._load_account() is not None

        self.heading.text = (
            "APP LOGIN" if exists else "CREATE YOUR APP LOGIN"
        )
        self.action.text = "LOGIN" if exists else "CREATE ACCOUNT"
        self.app_id.hint_text = "App ID"
        self.password.hint_text = (
            "Password"
            if exists
            else "Choose password (12+ characters)"
        )
        self.message.text = (
            "Enter your local app credentials."
            if exists
            else "Create an ID and a strong password for this device."
        )
        self.message.color = MUTED

    # Authentication logic below is preserved.

    def submit(self, *_):
        app_id = self.app_id.text.strip()
        password = self.password.text

        if not app_id or not password:
            self.message.text = "Enter both App ID and password."
            self.message.color = RED
            return

        account = self._load_account()

        if account is None:
            if len(password) < 12:
                self.message.text = "Use a password with at least 12 characters."
                self.message.color = RED
                return

            salt = secrets.token_bytes(16)
            account = {
                "app_id": app_id,
                "salt": salt.hex(),
                "password_hash": derive_hash(password, salt),
                "iterations": ITERATIONS,
            }

            try:
                os.makedirs(
                    os.path.dirname(self.account_file),
                    exist_ok=True,
                )
                with open(
                    self.account_file,
                    "x",
                    encoding="utf-8",
                ) as f:
                    json.dump(account, f)

            except FileExistsError:
                self.message.text = "Account setup changed. Try login again."
                self.message.color = RED
                self._refresh_mode()
                return

            except OSError:
                self.message.text = "Could not save account on this device."
                self.message.color = RED
                return

            self.message.text = "Account created. Opening dashboard..."
            self.message.color = PURPLE
            self.password.text = ""
            self.on_login()
            return

        try:
            salt = bytes.fromhex(account["salt"])
            expected = account["password_hash"]
            actual = derive_hash(password, salt)

            valid = (
                hmac.compare_digest(app_id, account["app_id"])
                and hmac.compare_digest(actual, expected)
            )

        except (KeyError, ValueError, TypeError):
            valid = False

        if not valid:
            self.message.text = "Incorrect App ID or password."
            self.message.color = RED
            self.password.text = ""
            return

        self.message.text = "Login successful."
        self.password.text = ""
        self.on_login()
