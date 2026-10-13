[app]
title = GARRY V7
package.name = garryv7
package.domain = com.garry.v7
source.dir =.
source.include_exts = py,png,jpg,kv,atlas,json
version = 0.1
requirements = python3,kivy==2.3.0,kivymd,requests,certifi,urllib3,pillow
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license_agreement = True

[buildozer]
log_level = 2
warn_on_root = 1

# p4a
p4a.url = https://github.com/kivy/python-for-android
p4a.branch = master
