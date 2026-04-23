[app]
title = GimRoutine
package.name = gimroutine
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,json
source.include_patterns = service_account.json,gimrutine-493121-84a3decf76ac.json,config.json,data/*
version = 0.1
requirements = python3,kivy==2.3.0,pillow,gspread,google-auth,requests,google-auth-httplib2,cryptography,cffi
android.api = 33
android.minapi = 21
android.sdk = 33
android.ndk = 25
android.permissions = INTERNET
android.arch = arm64-v8a
android.allow_backup = True
android.target_sdk_version = 33
android.manifest_orientation = portrait
# Note: OpenCV and pytesseract are not trivially available on Android via pip.
# OCR on Android should use ML Kit or a native tess/tess-two recipe.
# If you add opencv or other recipes, include them here.
presplash.filename = %(source.dir)s/data/presplash.png

[buildozer]
log_level = 2
warn_on_root = 1
android.accept_licenses = True

[buildozer:extra]
# Include your service account JSON if you want to bundle it (or put it on device manually)
# (Be careful with secrets bundled in the APK.)
include_exts = json
