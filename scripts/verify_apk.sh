#!/usr/bin/env bash
# verify_apk.sh - device-free verification for Gboard/PixelBoard patch outputs.
#
#   scripts/verify_apk.sh single <apk> [--profile p.json]
#   scripts/verify_apk.sh compare <stock.apk> <patched.apk>
#
# Checks: sha256, zip integrity, package/versionCode/versionName (androguard;
# aapt2 badging when available), dex inventory, signature scheme verification
# + signer certs (apksig), and optionally the fail-closed fingerprint anchors.
# No Google binaries are fetched or produced by this script.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="${TOOLS_DIR:-./tools}"
export JAVA_HOME="${JAVA_HOME:-$(ls -d "$TOOLS"/jdk-21* 2>/dev/null || true)}"
[ -n "$JAVA_HOME" ] && export PATH="$JAVA_HOME/bin:$PATH"

info() { echo "  $1"; }

single() {
  local apk="$1" profile="${2:-}"
  echo "== $apk"
  info "sha256: $(sha256sum "$apk" | cut -d' ' -f1)"
  unzip -t "$apk" >/dev/null && info "zip integrity: OK" || { echo "  zip CORRUPT"; return 1; }
  info "dex entries: $(unzip -l "$apk" | grep -cE 'classes[0-9]*\.dex')"
  python3 - "$apk" <<'PY'
import sys
from loguru import logger
logger.remove()
from androguard.core.apk import APK
a = APK(sys.argv[1])
print("  valid APK:", a.is_valid_APK())
print("  package:", a.get_package())
print("  versionCode:", a.get_androidversion_code(), " versionName:", a.get_androidversion_name())
print("  minSdk:", a.get_min_sdk_version(), " targetSdk:", a.get_target_sdk_version())
print("  abis:", sorted({f.split('/')[1] for f in a.get_files() if f.startswith('lib/')}) or "none")
PY
  if [ -x "$TOOLS/aapt2-extract/aapt2" ]; then
    "$TOOLS/aapt2-extract/aapt2" dump badging "$apk" 2>/dev/null | grep -E "^package|sdkVersion|targetSdkVersion|native-code" | sed 's/^/  aapt2: /'
  fi
  if [ -f "$TOOLS/classes/MiniApkSigner.class" ]; then
    java -cp "$TOOLS/apksig-8.3.0.jar:$TOOLS/classes" MiniApkSigner verify "$apk" | sed 's/^/  /'
  else
    info "(apksig frontend not built; skipping signature verification)"
  fi
  if [ -n "$profile" ]; then
    python3 "$ROOT/standalone-patcher/dex_patch.py" analyze --apk "$apk" \
      --profile "$profile" --workdir /tmp/verify-analyze \
      | python3 -c "
import json, sys
r = json.load(sys.stdin)
for k, hits in r['fingerprint_hits'].items():
    state = ('FOUND at ' + hits[0]['dex'] + ' ' + str(hits[0]['method'])) if hits else 'MISSING'
    print('  fingerprint', k + ':', state)
for k, m in r['methods'].items():
    print('  method', k + ':', ('found in ' + m['dex']) if 'dex' in m else 'NOT FOUND')
"
  fi
}

compare() {
  local stock="$1" patched="$2"
  echo "== compare"
  python3 - "$stock" "$patched" <<'PY'
import sys
from loguru import logger
logger.remove()
from androguard.core.apk import APK
s, p = APK(sys.argv[1]), APK(sys.argv[2])
for label, a, b in [("package", s.get_package(), p.get_package()),
                    ("versionCode", s.get_androidversion_code(), p.get_androidversion_code()),
                    ("versionName", s.get_androidversion_name(), p.get_androidversion_name())]:
    flag = "SAME" if a == b else "DIFFERENT"
    print("  %s: %s (%r vs %r)" % (label, flag, a, b))
PY
  for f in "$stock" "$patched"; do
    java -cp "$TOOLS/apksig-8.3.0.jar:$TOOLS/classes" MiniApkSigner verify "$f" 2>/dev/null | grep signer | sed "s|^|  $(basename "$f") |"
  done
  echo "  note: a DIFFERENT signer is expected when the patched build is re-signed"
  echo "  with a non-Google key (PixelBoard ships a signature-check bypass + package rename)."
}

case "${1:-}" in
  single)  single "${2:?apk}" "${4:-}" ;;
  compare) compare "${2:?stock}" "${3:?patched}" ;;
  *) echo "usage: $0 single <apk> [--profile p.json] | compare <stock.apk> <patched.apk>"; exit 2 ;;
esac
