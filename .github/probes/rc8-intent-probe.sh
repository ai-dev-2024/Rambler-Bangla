#!/usr/bin/env bash
# Review-only, four independent entry attempts. All screenshots/XML/logs are private, encrypted by workflow.
set -u
mkdir -p probe-evidence
adb wait-for-device
adb install --no-streaming -r "$APK_PATH" > probe-evidence/install.txt 2>&1 || exit 1
adb shell pm path "$PKG" > probe-evidence/installed-package-path.txt 2>&1
adb shell am force-stop "$PKG" >/dev/null 2>&1 || true
probe() {
  local tag="$1"; shift
  mkdir -p "probe-evidence/$tag"
  adb shell input keyevent KEYCODE_HOME >/dev/null 2>&1 || true
  sleep 2
  adb shell log -t Rc8Probe "BEGIN-$tag" >/dev/null 2>&1 || true
  printf '%q ' adb shell am start -W "$@" > "probe-evidence/$tag/command.txt"; echo >> "probe-evidence/$tag/command.txt"
  adb shell am start -W "$@" > "probe-evidence/$tag/start-out.txt" 2> "probe-evidence/$tag/start-err.txt"
  echo "$?" > "probe-evidence/$tag/start-rc.txt"
  sleep 3
  adb shell dumpsys window > "probe-evidence/$tag/window.txt" 2>&1
  adb shell dumpsys activity activities > "probe-evidence/$tag/activities.txt" 2>&1
  adb shell uiautomator dump /sdcard/window.xml > "probe-evidence/$tag/uiautomator-out.txt" 2>&1
  adb pull /sdcard/window.xml "probe-evidence/$tag/window.xml" >/dev/null 2>&1 || true
  adb shell screencap -p /sdcard/screen.png >/dev/null 2>&1
  adb pull /sdcard/screen.png "probe-evidence/$tag/screen.png" >/dev/null 2>&1 || true
  adb logcat -b events -d -v threadtime > "probe-evidence/$tag/events.txt" 2>&1
  adb logcat -b main -d -v threadtime > "probe-evidence/$tag/main.txt" 2>&1
  adb shell am force-stop "$PKG" >/dev/null 2>&1 || true
}
# 1. Known private component: confirm denial, never bypass app export policy.
probe private -n "$PKG/com.akshaykadam.pixelboard.extension.settings.GboardPatchesSettingsActivity"
# 2. Exported settings component from the pinned APK manifest.
probe settings -n "$PKG/com.google.android.apps.inputmethod.latin.preference.SettingsActivity"
# 3. Exported launcher, explicit component; capture first-run UI or settings navigation opportunity.
probe launcher -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n "$PKG/com.google.android.libraries.inputmethod.launcher.LauncherActivity"
# Launcher follow-up, only if the UI really shows the observed first-run Done or Settings gear.
# Each tap and post-tap snapshot is saved. No blind coordinate taps.
launcher_dir=probe-evidence/launcher
adb shell am start -W -a android.intent.action.MAIN -c android.intent.category.LAUNCHER \
  -n "$PKG/com.google.android.libraries.inputmethod.launcher.LauncherActivity" \
  > "$launcher_dir/reopen-out.txt" 2> "$launcher_dir/reopen-err.txt"
sleep 3
for label in Done Settings; do
  adb shell uiautomator dump /sdcard/window.xml > "$launcher_dir/before-$label-dump.txt" 2>&1
  adb pull /sdcard/window.xml "$launcher_dir/before-$label.xml" >/dev/null 2>&1 || true
  if [ -f "$launcher_dir/before-$label.xml" ]; then
    coords=$(python3 - "$launcher_dir/before-$label.xml" "$label" "$PKG" <<'PYTAP'
import re,sys,xml.etree.ElementTree as E
try:
    root=E.parse(sys.argv[1])
    for n in root.iter('node'):
        a=n.attrib
        if a.get('package')!=sys.argv[3]: continue
        if sys.argv[2].lower() not in ((a.get('text','')+' '+a.get('content-desc','')).lower().split()): continue
        b=list(map(int,re.findall(r'\d+',a.get('bounds',''))))
        if len(b)==4 and b[2]>b[0] and b[3]>b[1]:
            print((b[0]+b[2])//2,(b[1]+b[3])//2);break
except Exception: pass
PYTAP
)
    if [[ "$coords" =~ ^[0-9]+[[:space:]][0-9]+$ ]]; then
      read -r x y <<< "$coords"
      printf '%s %s\n' "$x" "$y" > "$launcher_dir/tap-$label.txt"
      adb shell input tap "$x" "$y"; sleep 3
    else
      echo "No package-owned exact $label target" > "$launcher_dir/tap-$label.txt"
    fi
  fi
  adb shell dumpsys window > "$launcher_dir/after-$label-window.txt" 2>&1
  adb shell uiautomator dump /sdcard/window.xml > "$launcher_dir/after-$label-dump.txt" 2>&1
  adb pull /sdcard/window.xml "$launcher_dir/after-$label.xml" >/dev/null 2>&1 || true
  adb shell screencap -p /sdcard/screen.png >/dev/null 2>&1
  adb pull /sdcard/screen.png "$launcher_dir/after-$label.png" >/dev/null 2>&1 || true
done
adb logcat -b events -d -v threadtime > "$launcher_dir/after-navigation-events.txt" 2>&1
adb logcat -b main -d -v threadtime > "$launcher_dir/after-navigation-main.txt" 2>&1
adb shell am force-stop "$PKG" >/dev/null 2>&1 || true
# 4. Exact package-only intent and flags that yielded result -91 in rc8.
probe package-only --activity-clear-task -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -f 0x10008000 -p "$PKG"
