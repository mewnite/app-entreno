[app]
title = GimRoutine
package.name = gimroutine
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,json
version = 0.1
requirements = python3,kivy==2.3.0,pillow,gspread,google-auth,requests,google-auth-httplib2
# Note: OpenCV and pytesseract are not trivially available on Android via pip.
# OCR on Android should use ML Kit or a native tess/tess-two recipe.
# If you add opencv or other recipes, include them here.
presplash.filename = %(source.dir)s/data/presplash.png

# Add service account credentials (place your service_account.json in the app directory)
# The app will look for it in internal storage first, then in app assets
# SECURITY WARNING: Bundling service account keys in the APK is convenient but risky.
# If the APK is compromised, attackers could extract the credentials and access your Google services.
# Consider alternative approaches: download credentials at runtime, use Android Keystore, or require manual installation.
android.add_src = service_account.json

[buildozer]
log_level = 2
warn_on_root = 1
android.accept_licenses = True

[app:android]
android.api = 33
android.minapi = 21
android.sdk = 33
android.ndk = 25
android.permissions = INTERNET, CAMERA, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
android.arch = arm64-v8a
android.allow_backup = True
android.backup_rules = backup_rules.xml
android.meta_data =
android.target_sdk_version = 33
android.manifest_orientation = portrait
android.gradle_dependencies = com.android.support:support-v4:28.0.0
p4a.source_dir = .
p4a.local_recipes = ./p4a-recipes

[buildozer:extra]
# Include your service account JSON if you want to bundle it (or put it on device manually)
# (Be careful with secrets bundled in the APK.)
include_exts = json
