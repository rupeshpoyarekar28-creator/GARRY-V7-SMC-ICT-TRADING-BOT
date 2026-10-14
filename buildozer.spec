[app]
title = GARRY V7
package.name = garryv7
package.domain = com.garry.v7
source.dir =.
source.include_exts = py,png,jpg,kv,atlas,json
version = 0.1
requirements = python3,kivy==2.3.1,kivymd==1.1.1,pillow,requests
orientation = portrait
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
p4a.branch = develop
p4a.bootstrap = sdl2

[buildozer]
log_level = 1
warn_on_root = 1
