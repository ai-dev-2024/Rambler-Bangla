#!/bin/bash
# Builds the empty-field harness APK on the runner (debug key, test only).
set -euo pipefail
cd "$(dirname "$0")"
BT="$ANDROID_HOME/build-tools/$(ls "$ANDROID_HOME/build-tools" | sort -V | tail -1)"
PLAT="$ANDROID_HOME/platforms/$(ls "$ANDROID_HOME/platforms" | sort -V | tail -1)/android.jar"
rm -rf out && mkdir -p out/cls out/dex
javac -source 8 -target 8 -nowarn -cp "$PLAT" -d out/cls src/t/h/Main.java
"$BT/d8" --min-api 26 --lib "$PLAT" --output out/dex $(find out/cls -name '*.class')
"$BT/aapt2" link --manifest AndroidManifest.xml -I "$PLAT" -o out/u.apk
(cd out/dex && zip -q ../u.apk classes.dex)
"$BT/zipalign" -f 4 out/u.apk out/a.apk
keytool -genkeypair -keystore out/k.jks -storepass harness -keypass harness -alias h -keyalg RSA -keysize 2048 -validity 3 -dname CN=harness >/dev/null 2>&1
"$BT/apksigner" sign --ks out/k.jks --ks-pass pass:harness --out out/harness.apk out/a.apk
echo "$(pwd)/out/harness.apk"
