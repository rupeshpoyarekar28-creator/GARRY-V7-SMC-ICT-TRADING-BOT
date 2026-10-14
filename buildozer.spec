[app]

Application identity

title = GARRY V7 SMC ICT TRADING BOT
package.name = garryv7
package.domain = com.garryv7

Application source

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf,otf

Python and Kivy dependencies

requirements = python3,kivy==2.3.0,websocket-client==1.8.0

App version

version = 1.0.0

Display settings

orientation = portrait
fullscreen = 0

Android SDK / NDK

android.api = 34
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.debug_artifact = apk

Network access for public Delta Exchange market data

android.permissions = INTERNET,ACCESS_NETWORK_STATE

Python-for-Android

p4a.branch = v2024.01.21
p4a.commit = 957a3e5
p4a.local_recipes = ./p4a_recipes

Build output

[buildozer]
log_level = 2
build_dir = .buildozer
bin_dir = bin
