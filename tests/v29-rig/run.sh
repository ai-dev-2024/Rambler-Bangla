#!/usr/bin/env bash
# V29 JVM rig: compile main's V29 sources (extension-src/.../rambler) against test-only stubs and run their checks.
#   bash tests/v29-rig/run.sh          (from the repo root; needs only a JDK 17+ and python3)
# Also checks that the OVERRIDE block in GboardRamblerLoanSpell.java matches data/loanspell/overrides.tsv
# (gen_java.py is run on a scratch copy; nothing in the tree is rewritten).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RIG="$ROOT/tests/v29-rig"
PKG=com/akshaykadam/pixelboard/extension/rambler
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
FAIL=0

# 1. LoanTable.java is generated, not committed: generate it on a scratch copy with the repo's own generator.
mkdir -p "$WORK/gen/extension-src/$PKG" "$WORK/gen/data"
cp -r "$ROOT/data/loanspell" "$WORK/gen/data/"
cp "$ROOT/extension-src/$PKG/GboardRamblerLoanSpell.java" "$WORK/gen/extension-src/$PKG/"
(cd "$WORK/gen" && python3 data/loanspell/gen_java.py >/dev/null) || { echo "  FAIL: gen_java.py"; exit 1; }
if cmp -s "$ROOT/extension-src/$PKG/GboardRamblerLoanSpell.java" "$WORK/gen/extension-src/$PKG/GboardRamblerLoanSpell.java"; then
  echo "  PASS: LoanSpell OVERRIDE block matches data/loanspell/overrides.tsv"
else
  echo "  FAIL: LoanSpell OVERRIDE block is out of date; run: python3 data/loanspell/gen_java.py"; FAIL=1
fi

# 2. Compile main's sources + generated table + stubs + test. The shipped-class stubs never enter a release build.
mkdir -p "$WORK/classes"
javac -encoding UTF-8 -nowarn -d "$WORK/classes" \
  "$ROOT"/extension-src/$PKG/*.java \
  "$WORK/gen/extension-src/$PKG/GboardRamblerLoanTable.java" \
  "$RIG"/stubs/$PKG/*.java "$RIG"/src/$PKG/*.java 2>&1 | grep -v '^Note:' ; C=${PIPESTATUS[0]}
[ "$C" -eq 0 ] || { echo "  FAIL: V29 rig does not compile"; exit 1; }

# 3. Run every tests/v29-rig/src/**/V29*Test.java and add up their "<Name>: N passed, M failed" lines.
P=0; F=0; X=0
for t in $(cd "$RIG/src" && find . -name 'V29*Test.java' | sort); do
  cls="$(echo "${t#./}" | sed 's|\.java$||; s|/|.|g')"
  out="$(java -Dfile.encoding=UTF-8 -Drig.fixtures="$RIG/fixtures" ${RIG_TRACE:+-Drig.trace="$RIG_TRACE"} -cp "$WORK/classes" "$cls" "$ROOT")"; rc=$?
  echo "$out"
  line="$(echo "$out" | grep -E '^[A-Za-z0-9]+: [0-9]+ passed, [0-9]+ failed' | tail -1)"
  [ -n "$line" ] || { echo "  FAIL: $cls printed no summary (exit $rc)"; F=$((F+1)); FAIL=1; continue; }
  P=$((P + $(echo "$line" | sed -E 's/.*: ([0-9]+) passed.*/\1/')))
  F=$((F + $(echo "$line" | sed -E 's/.* ([0-9]+) failed.*/\1/')))
  X=$((X + $(echo "$line" | grep -oE '\(([0-9]+) xfail\)' | grep -oE '[0-9]+' || echo 0)))
  [ "$rc" -eq 0 ] || FAIL=1
done
echo "V29 RIG: $P passed, $F failed ($X xfail)"
exit $FAIL
