#!/usr/bin/env bash
# Full static test suite for the Bengali script patch.
# 1. Policy unit tests (JVM)            4. Fail-closed negative tests
# 2. Fixture APK build                  5. APK parse/signature validation
# 3. End-to-end patch + wiring check
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source $HOME/tools/tool-env.sh
PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL: $1"; }
check() { if [ "$1" -eq 0 ]; then ok "$2"; else bad "$2"; fi }

echo "== 1. policy unit tests"
mkdir -p /tmp/policy-build
javac -d /tmp/policy-build \
  "$ROOT"/extension-src/com/akshaykadam/pixelboard/extension/ramblerlite/*.java \
  "$ROOT"/tests/src/com/akshaykadam/pixelboard/extension/ramblerlite/*.java \
  && java -cp /tmp/policy-build \
  com.akshaykadam.pixelboard.extension.ramblerlite.GboardRamblerLiteScriptRuntimeTest
check $? "policy unit tests (51 assertions)"

echo "== 2. fixture build"
bash "$ROOT/fixtures/build_fixture.sh" >/tmp/fixture-build.log 2>&1
check $? "fixture APK builds (smali + d8 + aapt2 + sign)"

echo "== 3. end-to-end patch"
python3 "$ROOT/standalone-patcher/dex_patch.py" analyze \
  --apk "$ROOT/fixtures/out/fixture-stock.apk" \
  --profile "$ROOT/fixtures/fixture-profile.json" \
  --workdir /tmp/t-analyze >/tmp/t-analyze.json 2>&1
check $? "analyze resolves anchors and fingerprints"
grep -q '"hinglish_override_rule": \[' /tmp/t-analyze.json \
  && python3 -c "
import json
r = json.load(open('/tmp/t-analyze.json'))
assert r['fingerprint_hits']['hinglish_override_rule'], 'no rule hit'
assert r['fingerprint_hits']['lite_cleanup_prompt'], 'no prompt hit'
" ; check $? "analyze reports both fingerprint hits"

python3 "$ROOT/standalone-patcher/dex_patch.py" patch \
  --apk "$ROOT/fixtures/out/fixture-stock.apk" \
  --out "$ROOT/fixtures/out/fixture-patched.apk" \
  --profile "$ROOT/fixtures/fixture-profile.json" \
  --workdir /tmp/t-patch >/tmp/t-patch.json 2>&1
check $? "patch applies on matching fixture"

rm -rf /tmp/t-dis && mkdir -p /tmp/t-dis && cd /tmp/t-dis
unzip -o -q "$ROOT/fixtures/out/fixture-patched.apk" classes.dex
java -cp "$SMALI_CP" org.jf.baksmali.Main d classes.dex -o dis 2>/dev/null
grep -q 'selectHinglishOverrideRule' dis/kfd.smali; check $? "hook B (override rule) present"
grep -q 'rewriteCleanupPromptScriptGate' dis/kfd.smali; check $? "hook A (script gate) present"
grep -q 'move-object/from16 v3, v2' dis/kfd.smali; check $? "enabled-languages value saved to dedicated register"
! grep -q 'invoke-static/range {v4 .. v4}' dis/kfd.smali; check $? "hook args are distinct registers (no clobber)"
grep -q '3. Hinglish Override' dis/kfd.smali; check $? "stock rule string preserved as fail-safe input"
grep -q '.registers 14' dis/kfd.smali; check $? "register window grew exactly by 3 temps"
cd "$ROOT"

python3 "$ROOT/standalone-patcher/dex_patch.py" patch \
  --apk "$ROOT/fixtures/out/fixture-stock.apk" \
  --out "$ROOT/fixtures/out/fixture-patched-ext.apk" \
  --profile "$ROOT/fixtures/fixture-profile.json" \
  --extension-dex "$ROOT/fixtures/out/classes2.dex" \
  --workdir /tmp/t-patch-ext >/dev/null 2>&1
unzip -l "$ROOT/fixtures/out/fixture-patched-ext.apk" | grep -q 'classes3.dex'
check $? "--extension-dex merge adds classes3.dex"

echo "== 4. fail-closed negative tests"
python3 - "$ROOT" <<'PYEOF'
import json, sys
p = json.load(open(sys.argv[1] + '/fixtures/fixture-profile.json'))
p['fingerprints']['hinglish_override_rule']['sha256'] = '0' * 64
json.dump(p, open('/tmp/t-bad-profile.json', 'w'))
PYEOF
python3 "$ROOT/standalone-patcher/dex_patch.py" patch \
  --apk "$ROOT/fixtures/out/fixture-stock.apk" --out /tmp/t-should-not-exist.apk \
  --profile /tmp/t-bad-profile.json --workdir /tmp/t-neg1 >/tmp/t-neg1.log 2>&1
[ $? -eq 2 ] && [ ! -f /tmp/t-should-not-exist.apk ]
check $? "wrong fingerprint aborts with no output APK"

# tampered fixture: change one char of the stock rule in smali, rebuild, expect abort
rm -rf /tmp/t-tamper && cp -r "$ROOT/fixtures/src" /tmp/t-tamper
sed -i 's/Hinglish Override/Xinglish Override/' /tmp/t-tamper/kfd.smali
java -cp "$SMALI_CP" org.jf.smali.Main a /tmp/t-tamper -o /tmp/t-tampered.dex
cd /tmp && cp "$ROOT/fixtures/out/fixture-stock.apk" /tmp/t-tampered.apk \
  && zip -q /tmp/t-tampered.apk /tmp/t-tampered.dex 2>/dev/null
cd /tmp && mkdir -p z && cd z && rm -f classes.dex && unzip -o -q /tmp/t-tampered.apk classes.dex \
  && cp /tmp/t-tampered.dex classes.dex && zip -q /tmp/t-tampered.apk classes.dex && cd "$ROOT"
python3 "$ROOT/standalone-patcher/dex_patch.py" patch \
  --apk /tmp/t-tampered.apk --out /tmp/t-should-not-exist2.apk \
  --profile "$ROOT/fixtures/fixture-profile.json" --workdir /tmp/t-neg2 >/tmp/t-neg2.log 2>&1
[ $? -eq 2 ] && [ ! -f /tmp/t-should-not-exist2.apk ]
check $? "tampered stock string aborts with no output APK"

python3 "$ROOT/standalone-patcher/dex_patch.py" patch \
  --apk "$ROOT/fixtures/out/fixture-patched.apk" --out /tmp/t-double.apk \
  --profile "$ROOT/fixtures/fixture-profile.json" --workdir /tmp/t-neg3 >/tmp/t-neg3.log 2>&1
[ $? -eq 2 ]; check $? "re-patching an already patched build aborts (idempotency guard)"

echo "== 5. APK parse + signature validation"
java -cp "$TOOLS_DIR/apksig-8.3.0.jar:$TOOLS_DIR/classes" MiniApkSigner sign \
  "$ROOT/fixtures/out/fixture-debug.keystore" fixture-only fixture fixture-only \
  "$ROOT/fixtures/out/fixture-patched.apk" "$ROOT/fixtures/out/fixture-patched-signed.apk" >/dev/null
java -cp "$TOOLS_DIR/apksig-8.3.0.jar:$TOOLS_DIR/classes" MiniApkSigner verify \
  "$ROOT/fixtures/out/fixture-patched-signed.apk" | tee /tmp/t-verify.log
grep -q 'verified=true' /tmp/t-verify.log && grep -q 'v2=true' /tmp/t-verify.log
check $? "patched+resigned fixture passes APK Signature Scheme v2 verification"
python3 - "$ROOT" <<'PYEOF'
import sys
from loguru import logger
logger.remove()
from androguard.core.apk import APK
for name in ("fixture-stock.apk", "fixture-patched-signed.apk"):
    a = APK(sys.argv[1] + "/fixtures/out/" + name)
    assert a.is_valid_APK(), name + " not valid"
    print(" ", name, "| pkg:", a.get_package(),
          "| vc:", a.get_androidversion_code(),
          "| vn:", a.get_androidversion_name(),
          "| dexes:", len(list(a.get_all_dex())))
print("  androguard: both APKs parse as valid, package/version read back")
PYEOF
check $? "androguard parses stock+patched fixture APKs"

echo
echo "==================================="
echo "TEST SUITE: $PASS passed, $FAIL failed"
exit $([ $FAIL -eq 0 ] && echo 0 || echo 1)
