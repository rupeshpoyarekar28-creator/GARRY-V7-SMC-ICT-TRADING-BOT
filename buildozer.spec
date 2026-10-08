[app]

# ============================================================
# GARRY V7 SMC ICT TRADING BOT
# Clean, self-contained Android application
# ============================================================

# Application identity
title = GARRY V7 SMC ICT TRADING BOT
package.name = garryv7
package.domain = com.garryv7

# Source directory
source.dir = .

# Files to include in the APK
source.include_exts = py,png,jpg,jpeg,kv,atlas

# Python runtime dependencies
requirements = python3,kivy

# Application entry point
# main.py is the ONLY application entry point.
android.entrypoint = org.kivy.android.PythonActivity

# Application version
version = 1.0.0

# Screen orientation
orientation = portrait

# Fullscreen disabled
fullscreen = 0


# ============================================================
# ANDROID CONFIGURATION
# ============================================================

# Target Android API
android.api = 35

# Minimum supported Android API
android.minapi = 24

# Android NDK
android.ndk = 28c
android.ndk_path = /usr/local/lib/android/sdk/ndk/28.2.13676358

# NDK API
android.ndk_api = 24

# Build only for modern 64-bit Android devices
android.archs = arm64-v8a

# Automatically accept Android SDK licenses in CI
android.accept_sdk_license = True


# ============================================================
# BUILD CONFIGURATION
# ============================================================
p4a.local_recipes = ./p4a_recipes
[buildozer]

# Buildozer log level
log_level = 2

# Build directory
build_dir = .buildozer

# APK output directory
bin_dir = bin
