[app]
title = GARRY V7
package.name = garryv7
package.domain = com.garry.v7

source.dir =.
source.include_exts = py,png,jpg,kv,atlas,json,txt
source.exclude_exts = spec,md,yml,yaml

version = 0.1
version.regex = __version__ = ['"](.*)['"]
version.filename = %(source.dir)s/main.py

requirements = python3,kivy==2.3.0,kivymd,requests,certifi,urllib3,pillow
orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.build_tools_version = 33.0.2
android.accept_sdk_license_agreement = True
android.ant = auto

[buildozer]
log_level = 2
warn_on_root = 1

[app:requirements]
# extra

# p4a
p4a.bootstrap = sdl2
p4a.url = https://github.com/kivy/python-for-android
p4a.branch = master
p4a.port =
