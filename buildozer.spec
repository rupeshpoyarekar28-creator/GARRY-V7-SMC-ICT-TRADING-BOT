[app]

# Application identity
title = GARRY V7 SMC ICT TRADING BOT
package.name = garryv7
package.domain = com.garryv7

# Source
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json

# Keep dependencies minimal for Android compatibility
requirements = python3,kivy,websocket-client

version = 1.0.0
orientation = portrait
fullscreen = 0

# Android SDK/NDK
android.api = 34
android.minapi = 24
android.ndk = 25b
android.ndk_path = /usr/local/lib/android/sdk/ndk/25.2.9519653
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.debug_artifact = apk

# Required for public Delta Exchange market-data HTTP requests
android.permissions = INTERNET,ACCESS_NETWORK_STATE

# python-for-android
p4a.branch = v2024.01.21
p4a.commit = 957a3e5
p4a.local_recipes = ./p4a_recipes

[buildozer]
log_level = 2
build_dir = .buildozer
bin_dir = bin
