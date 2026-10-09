
"""
GARRY V7 - Local Login / First-time Account Setup

This is a local prototype, not production-grade authentication.
Credentials are stored as a salted password hash, not plain text.
"""

import hashlib
import hmac
import json
import os
import secrets

from kivy.app import App
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

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
            padding=(dp(28), dp(24)),
            spacing=dp(14),
            **kwargs,
        )
        self.on_login = on_login
        self.account_file = os.path.join(
            App.get_running_app().user_data_dir,
            "local_account.json",
        )

        self.add_widget(Label(size_hint_y=0.18))

        self.add_widget(Label(
            text="[b]GARRY V7[/b]",
            markup=True,
            font_size=sp(30),
            color=WHITE,
            size_hint_y=None,
            height=dp(48),
        ))
        self.add_widget(Label(
            text="SMC / ICT TRADING BOT",
            font_size=sp(13),
            color=PURPLE,
            size_hint_y=None,
            height=dp(28),
        ))

        self.heading = Label(
            text="CREATE YOUR APP LOGIN",
            font_size=sp(17),
            bold=True,
            color=WHITE,
            size_hint_y=None,
            height=dp(38),
        )
        self.add_widget(self.heading)

        self.app_id = TextInput(
            hint_text="Choose App ID",
            multiline=False,
            size_hint_y=None,
            height=dp(50),
            background_normal="",
            background_active="",
            background_color=CARD2,
            foreground_color=WHITE,
            hint_text_color=MUTED,
            padding=(dp(12), dp(14)),
        )
        self.password = TextInput(
            hint_text="Choose password (12+ characters)",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(50),
            background_normal="",
            background_active="",
            background_color=CARD2,
            foreground_color=WHITE,
            hint_text_color=MUTED,
            padding=(dp(12), dp(14)),
        )
        self.add_widget(self.app_id)
        self.add_widget(self.password)

        self.message = Label(
            text="First launch: create your account on this device.",
            font_size=sp(12),
            color=MUTED,
            size_hint_y=None,
            height=dp(52),
        )
        self.add_widget(self.message)

        self.action = Button(
            text="CREATE ACCOUNT",
            size_hint_y=None,
            height=dp(52),
            background_normal="",
            background_color=PURPLE,
            color=WHITE,
            bold=True,
        )
        self.action.bind(on_release=self.submit)
        self.add_widget(self.action)

        self.add_widget(Label(size_hint_y=0.2))
        self._refresh_mode()

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
            "Password" if exists else "Choose password (12+ characters)"
        )
        self.message.text = (
            "Enter your local app credentials."
            if exists
            else "Create an ID and a strong password for this device."
        )

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
                os.makedirs(os.path.dirname(self.account_file), exist_ok=True)
                with open(self.account_file, "x", encoding="utf-8") as f:
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
