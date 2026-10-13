[app]

# App Details
title = GARRY V7
package.name = garryv7
package.domain = com.rupes.garryv7

source.dir =.
source.include_exts = py,png,jpg,kv,atlas,json,txt
source.include_patterns = app/*,data/*,strategy/*,*.kv
source.exclude_exts = spec,md
source.exclude_patterns = bin,venv,.git,__pycache__

version = 7.0
version.regex = __version__ = ['"]([^'"]+)['"]
version.filename = %(source.dir)s/main.py

# --- HA SARVAT MAHATVACHI LINE AHE - SSL FIX SATHI ---
requirements = python3,kivy==2.3.0,kivymd==1.2.0,requests,urllib3,charset-normalizer,idna,certifi,openssl,pillow

# Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE

# Application Icon (jar tuzyakade nasel tar he line comment kar)
# icon.filename = %(source.dir)s/app/icon.png
# presplash.filename = %(source.dir)s/app/presplash.png

[buildozer]

log_level = 2
warn_on_root = 1

# --- ANDROID BUILD ---

# (int) Target API
android.api = 33

# (int) Minimum API
android.minapi = 21

# (str) NDK version
android.ndk = 25b

# (str) Antik SDK path nahi lagat - auto download hoil

# Bootstrap
p4a.bootstrap = sdl2

# Whitelist for certifi
p4a.whitelist = lib-dynload,certifi

# Orientation
orientation = portrait

# Allow backup
android.allow_backup = True

# Fullscreen nako
fullscreen = 0

# Keep screen on
android.wakelock = False

# Android arch - donhi sathi
android.archs = arm64-v8a, armeabi-v7a

# --- DEBUG / RELEASE ---
# debug sathi khali kahich badlu nakos

# (str) Python-for-android branch
p4a.branch = master

# (list) Extra args
p4a.extra_args = --with-recipes=openssl,requests,certifi

[app:darwin]

# Mac sathi nako

[app:linux]

# Linux sathi nako
