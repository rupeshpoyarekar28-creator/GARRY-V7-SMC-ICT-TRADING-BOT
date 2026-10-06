[app]

# GARRY V7 application identity
title = GARRY V7 SMC ICT TRADING BOT
package.name = garryv7
package.domain = com.garryv7

# Source directory
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas

# Python dependencies required by the application
requirements = python3,kivy==2.3.1

# Application entry point
# main.py is the only application entry point.
orientation = portrait

# Android application settings
fullscreen = 0

# Version
version = 1.0.0


[buildozer]

# Log level
log_level = 2

# Warning: do not use this build directory as source code.
# Buildozer will create its own build files here.
build_dir = .buildozer

# APK output directory
bin_dir = bin


[app:android]

# Android API configuration
android.api = 35
android.minapi = 23

# Android architecture
android.archs = arm64-v8a

# NDK version
android.ndk = 28c

# Accept Android SDK licenses during automated build
android.accept_sdk_license = True
