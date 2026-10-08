[app]

# (str) Title of your application
title = GARRY V7 SMC ICT TRADING BOT

# (str) Package name
package.name = garryv7

# (str) Package domain
package.domain = com.garryv7

# (str) Source code directory
source.dir = .

# (str) List of source file extensions
source.include_exts = py,png,jpg,jpeg,kv,atlas,json

# (list) Application requirements
# IMPORTANT: Keep this minimal for the first successful APK build.
requirements = python3,kivy

# (str) Application version
version = 1.0.0

# (str) Supported orientation
orientation = portrait

# (bool) Fullscreen
fullscreen = 0


# ------------------------------------------------------------------
# ANDROID
# ------------------------------------------------------------------

# Android API
android.api = 34

# Minimum Android API
android.minapi = 24

# Android NDK version
android.ndk = 25b

# Exact NDK path used by GitHub Actions
android.ndk_path = /usr/local/lib/android/sdk/ndk/25.2.9519653

# NDK API
android.ndk_api = 24

# Build only 64-bit ARM
android.archs = arm64-v8a

# Accept Android SDK licenses
android.accept_sdk_license = True

# Debug APK
android.debug_artifact = apk


# ------------------------------------------------------------------
# PYTHON-FOR-ANDROID
# ------------------------------------------------------------------

# Stable p4a release
p4a.branch = v2024.01.21

# Exact p4a commit for deterministic build
p4a.commit = 957a3e5

# Local custom recipes
# Kept available, but charset-normalizer is NOT requested in requirements.
p4a.local_recipes = ./p4a_recipes


# ------------------------------------------------------------------
# BUILDOSER
# ------------------------------------------------------------------

[buildozer]

log_level = 2

build_dir = .buildozer

bin_dir = bin
