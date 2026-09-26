#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
BT="$ANDROID_HOME/build-tools/$(ls "$ANDROID_HOME/build-tools" | sort -V | tail -1)"
PLAT="$ANDROID_HOME/platforms/$(ls "$ANDROID_HOME/platforms" | sort -V | tail -1)/android.jar"
mkdir -p out/cls out/dex
javac -source 8 -target 8 -nowarn -cp "$PLAT" -d out/cls src/test/clip/fixture/MainActivity.java
"$BT/d8" --min-api 32 --lib "$PLAT" --output out/dex $(find out/cls -name '*.class')
"$BT/aapt2" link --manifest AndroidManifest.xml -I "$PLAT" -o out/u.apk
(cd out/dex && zip -q ../u.apk classes.dex)
"$BT/zipalign" -f 4 out/u.apk out/a.apk
keytool -genkeypair -keystore out/k.jks -storepass fixture -keypass fixture -alias test -keyalg RSA -keysize 2048 -validity 3 -dname CN=fixture >/dev/null 2>&1
"$BT/apksigner" sign --ks out/k.jks --ks-pass pass:fixture --out out/fixture.apk out/a.apk
"$BT/apksigner" verify out/fixture.apk
echo "$(pwd)/out/fixture.apk"
