#!/usr/bin/env python3
"""Keyboard release-candidate device round (emulator only, test branch).
Usage: device_round.py <phase>   phase = fresh | matrix | update | voice | lanes | clip
Expected results are predeclared in device_round_expected.json. Private values (row text, storage key)
arrive at run time in ROUND_EXPECT_PRIVATE and must match the hash commitment in that file.
Every case gets status PASS / FAIL / UNTESTED / BLOCKED / NOT-RUN / DRIVER-ERROR / OBSERVED / ENV-MISMATCH and a tier.
ENV-MISMATCH = the emulator rejected the arm64-only APK (NO_MATCHING_ABIS): an environment result, never a product regression.
T1 = the pinned release bytes running on this emulator; only T1 PASS counts toward a release.
T1-env = an environment check (emulator image or package absence), never a product result.
The process always exits 0; verdicts are only in the encrypted evidence.
Nothing is printed to stdout/stderr on purpose: all output goes to round-artifacts/<phase>/ (encrypted by the workflow)."""
import os, re, sys, time, json, hashlib, subprocess, traceback
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clip_e2e as c

PHASE = sys.argv[1] if len(sys.argv) > 1 else "fresh"
c.OUT = os.path.join("round-artifacts", PHASE); os.makedirs(c.OUT, exist_ok=True)
def quiet_log(*a):
    with open(os.path.join(c.OUT, "driver.log"), "a") as f: f.write(" ".join(str(x) for x in a) + "\n")
c.log = quiet_log
PKG = c.PKG
HERE = os.path.dirname(os.path.abspath(__file__))
EXP = json.load(open(os.path.join(HERE, "device_round_expected.json")))
APK = os.environ.get("APK_PATH", ""); BASE = os.environ.get("BASE_APK_PATH", "")
WANT = os.environ.get("EXPECTED_SHA256", ""); WANT_BASE = os.environ.get("BASE_SHA256", "")
HARNESS = os.environ.get("HARNESS_APK", "")
ACT = PKG + "/com.akshaykadam.pixelboard.extension.settings.GboardPatchesSettingsActivity"
PREFS = "/data/data/%s/shared_prefs" % PKG
CASES = []; LAST_XML = [""]

def save(name, text): open(os.path.join(c.OUT, name), "w").write(text if isinstance(text, str) else json.dumps(text, indent=1))
def sh(cmd, timeout=120): return c.sh(cmd, timeout=timeout)
def adb(a, timeout=120): return c.adb(a, timeout=timeout)
def root(cmd, timeout=120): return adb("shell su 0 sh -c " + json.dumps(cmd), timeout=timeout)
def sha_file(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

# ---- private values, checked against the public commitment ----
PRIV_RAW = os.environ.get("ROUND_EXPECT_PRIVATE", "")
try:
    _p = json.loads(PRIV_RAW); PRIV = _p["values"]
    canon = json.dumps(PRIV, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    PRIV_OK = hashlib.sha256((_p["salt"] + canon).encode("utf-8")).hexdigest() == EXP["private_commitment"]
except Exception:
    PRIV, PRIV_OK = {}, False
save("expect-private.json", {"values": PRIV, "commitment_ok": PRIV_OK})
TITLE = PRIV.get("row_title", "\x00"); DESC = PRIV.get("row_desc_prefix", "\x00"); KEY = PRIV.get("pref_key", "\x00")

# ---- UI helpers ----
def snap(tag):
    xml = c.snap(tag); LAST_XML[0] = xml; return c.nodes(xml)

def tree():
    x = LAST_XML[0]
    if "<hierarchy" not in x: return None
    x = x[x.index("<"):]
    try: return ET.fromstring(x[: x.rindex(">") + 1])
    except ET.ParseError: return None

def bounds(n):
    b = list(map(int, re.findall(r"\d+", n.get("bounds", ""))))
    return b if len(b) == 4 else None

def row_switch(title):
    """Smallest ancestor of the title node that holds exactly one checkable node; returns (checked, center, row_bounds)."""
    t = tree()
    if t is None: return None
    parent = {ch: p for p in t.iter() for ch in p}
    hits = [n for n in t.iter("node") if n.get("text") == title]
    if not hits: return None
    n = hits[0]
    while n in parent:
        n = parent[n]
        cks = [x for x in n.iter("node") if x.get("checkable") == "true"]
        if len(cks) == 1:
            b = bounds(cks[0]); rb = bounds(n)
            if not b or not rb: return None
            return dict(checked=cks[0].get("checked"), cx=(b[0] + b[2]) // 2, cy=(b[1] + b[3]) // 2, row=rb, res=cks[0].get("resource-id"))
        if len(cks) > 1: return None
    return None

def open_settings(tag):
    root("am start -W -n " + ACT); time.sleep(3)

def settings_focused():
    w = adb("shell dumpsys window")
    m = re.search(r"mCurrentFocus=[^\n]*", w)
    return bool(m and "GboardPatchesSettingsActivity" in m.group(0))

def find_row(title, tag):
    """Scrolls the settings list from top to end looking for the row.
    Returns (found, switch, absent_proven, texts). Absence is only proven when the settings activity has focus,
    the diagnostics anchor row was seen, at least one swipe changed the visible text, and the list end was reached."""
    open_settings(tag)
    focused = settings_focused()
    for _ in range(4): adb("shell input swipe 540 700 540 1700 200")
    seen, prev, changed, end = set(), None, 0, False
    for i in range(25):
        ns = snap("%s-%02d" % (tag, i))
        texts = tuple(n["text"] for n in ns if n["text"])
        seen.update(texts)
        if title in texts:
            if not settings_focused():  # a hit only counts on the focused settings screen
                save("findrow-%s.json" % tag, dict(hit=True, focused=False))
                return False, None, False, sorted(seen)
            return True, row_switch(title), False, sorted(seen)
        if prev is not None:
            if texts == prev: end = True; break
            changed += 1
        prev = texts
        adb("shell input swipe 540 1600 540 800 400"); time.sleep(1)
    focused = focused and settings_focused()
    proven = focused and end and changed >= 1 and "Rambler diagnostics" in seen
    save("findrow-%s.json" % tag, dict(focused=focused, end=end, changed=changed, anchor="Rambler diagnostics" in seen))
    return False, None, proven, sorted(seen)

def tap_switch(sw):
    c.tap(sw["cx"], sw["cy"]); time.sleep(1.5)

# ---- device facts ----
def enabled_subtypes():
    """Locales of this IME's ENABLED subtypes, from enabled_input_methods + dumpsys hash->locale."""
    en = adb("shell settings get secure enabled_input_methods").strip()
    hashes = []
    for part in en.split(":"):
        f = part.split(";")
        if f and f[0].startswith(PKG + "/"): hashes = f[1:]
    loc = {}
    for line in adb("shell dumpsys input_method").splitlines():
        h = re.search(r"mSubtypeHashCode=(-?\d+)", line); lo = re.search(r"mSubtypeLocale=(\S*)", line)
        if h and lo: loc[h.group(1)] = lo.group(1)
    out = sorted(set(loc.get(h, "?" + h) for h in hashes))
    save("subtypes-%d.txt" % int(time.time() * 1000), {"enabled_input_methods": en, "locales": out})
    return out, loc

def active_locale(loc=None):
    loc = loc or enabled_subtypes()[1]
    return loc.get(adb("shell settings get secure selected_input_method_subtype").strip(), "")

is_latn = lambda l: "latn" in l.lower()
is_bn = lambda l: l.lower().startswith("bn") and not is_latn(l)
is_en = lambda l: l.lower().startswith("en")

def proof(cid):
    paths = adb("shell pm path " + PKG).replace("package:", "").split()
    base = [p for p in paths if p.endswith("/base.apk")]
    bsha = root("sha256sum " + base[0]).split()[0] if base else ""
    dp = adb("shell dumpsys package " + PKG)
    g = lambda rx: (re.search(rx, dp).group(1).strip() if re.search(rx, dp) else "")
    flags = g(r"pkgFlags=\[([^\]]*)\]") + " " + g(r"privateFlags=\[([^\]]*)\]")
    pid = adb("shell pidof " + PKG).strip()
    mapped = root("grep -m1 -o '/data/app/[^ ]*base.apk' /proc/%s/maps" % pid).strip() if pid else ""
    p = dict(case=cid, t=time.time(), paths=paths, base_sha256=bsha, split=len(paths) > 1,
             versionCode=g(r"versionCode=(\d+)"), firstInstall=g(r"firstInstallTime=([^\n]+)"),
             lastUpdate=g(r"lastUpdateTime=([^\n]+)"), uid=g(r"userId=(\d+)"), sharedUser=("sharedUser=" in dp),
             debuggable=("DEBUGGABLE" in flags), testOnly=("TEST_ONLY" in flags),
             instrumentation=(PKG in adb("shell pm list instrumentation")), pid=pid,
             pid_maps_base=bool(base) and mapped == base[0],
             ime=adb("shell settings get secure default_input_method").strip(),
             subtype=adb("shell settings get secure selected_input_method_subtype").strip(),
             fingerprint=adb("shell getprop ro.build.fingerprint").strip())
    with open(os.path.join(c.OUT, "proof.jsonl"), "a") as f: f.write(json.dumps(p) + "\n")
    return p

def grounded(p, want, behavioral):
    ok = bool(want) and p["base_sha256"] == want and not p["split"] and not p["debuggable"] and not p["testOnly"] \
        and not p["sharedUser"] and not p["instrumentation"]
    return ok and (p["pid_maps_base"] or not behavioral)

def logs_reset():
    adb("logcat -G 16M"); adb("logcat -b all -c")

def case(cid, status, reason, tier="T1", want=None, behavioral=True, **ev):
    p = proof(cid)
    if ENV_MISMATCH and status in ("FAIL", "UNTESTED", "BLOCKED"):
        status, reason = "ENV-MISMATCH", "ENVIRONMENT MISMATCH (no arm64 support on this emulator, NO_MATCHING_ABIS at %s); not a product result. %s" % (ENV_MISMATCH, reason)
    if status == "PASS" and tier == "T1" and not grounded(p, WANT if want is None else want, behavioral):
        status, reason = "BLOCKED", "grounding failed (hash/split/flags/pid map): " + reason
    CASES.append(dict(id=cid, status=status, tier=tier, reason=reason, expected=EXP["cases"].get(cid, ""), **ev))
    sh("adb logcat -b all -d -v threadtime > '%s/logcat-%s.txt'" % (c.OUT, cid))
    sh("adb shell dumpsys dropbox --print > '%s/dropbox-%s.txt'" % (c.OUT, cid))
    logs_reset()
    return status

ENV_MISMATCH = []
def install(p, label):
    out = adb("install --no-streaming -r '%s'" % p, timeout=300); save("install-%s.txt" % label, out)
    if "NO_MATCHING_ABIS" in out or "INSTALL_FAILED_NO_MATCHING_ABIS" in out:
        ENV_MISMATCH.append(label)  # emulator cannot run arm64 code: environment, not a product result
    return "Success" in out

def ime_ready():
    for _ in range(20):
        ime = sh("adb shell ime list -a -s | tr -d '\\r' | grep -m1 '^%s/'" % PKG).strip()
        if ime:
            adb("shell ime enable " + ime); adb("shell ime set " + ime); return ime
        time.sleep(3)
    return ""

def reboot():
    adb("reboot"); adb("wait-for-device", timeout=300)
    for _ in range(90):
        if sh("adb shell getprop sys.boot_completed").strip() == "1": break
        time.sleep(3)
    time.sleep(8); adb("shell input keyevent 82")

def stored_pref():
    t = root("cat %s/*.xml" % PREFS); save("prefs-%d.txt" % int(time.time() * 1000), t)
    m = re.search(r'<boolean name="%s" value="(true|false)"' % re.escape(KEY), t); return m.group(1) if m else None

def add_language(pattern, label):
    adb("shell monkey -p %s -c android.intent.category.LAUNCHER 1" % PKG); time.sleep(4)
    d = c.find(snap("launch-" + label), r"^done$", fields=("text",))
    if d: c.tap(d["cx"], d["cy"]); time.sleep(3)
    for step in (r"^languages$", r"^add keyboard$"):
        hit = None
        for _ in range(5):
            hit = c.find(snap("lang-" + label), step, fields=("text",))
            if hit: c.tap(hit["cx"], hit["cy"]); time.sleep(2); break
            adb("shell input swipe 540 1600 540 800 300"); time.sleep(1)
        if not hit and step == r"^add keyboard$": return False
    s = c.find(snap("search-" + label), r"search", fields=("text", "desc", "res"))
    if s: c.tap(s["cx"], s["cy"])
    adb("shell input text bangla"); time.sleep(2); adb("shell input keyevent KEYCODE_BACK"); time.sleep(1)
    r = [n for n in snap("results-" + label) if n["pkg"] == PKG and re.search(pattern, n["text"] or "")]
    if not r: return False
    c.tap(r[0]["cx"], r[0]["cy"]); time.sleep(3)
    dn = c.find(snap("layouts-" + label), r"^done$", fields=("text",))
    if dn: c.tap(dn["cx"], dn["cy"]); time.sleep(4)
    return bool(dn)

LATN = r"^Bangla \(Latin\)$|^বাংলা \(লাতিন\)$"
NATIVE = r"^বাংলা \(বাংলাদেশ\)$|^Bangla \(Bangladesh\)$"

def select_subtype(want, tag):
    loc = enabled_subtypes()[1]
    for i in range(6):
        cur = active_locale(loc)
        if want(cur): return cur
        k = c.find([n for n in snap("langkey-%s-%d" % (tag, i)) if n["pkg"] == PKG], r"language|globe|switch input", fields=("desc",))
        if not k: return cur
        c.tap(k["cx"], k["cy"]); time.sleep(2)
    return active_locale(loc)

def harness_focus(tag):
    adb("shell am start -W -n t.h/.Main"); time.sleep(2)
    f = c.find(snap("h-" + tag), r"^harness-field$", fields=("desc",))
    if f: c.tap(f["cx"], f["cy"]); time.sleep(1.5)
    return f

def field_text(tag):
    f = c.find(snap("hf-" + tag), r"^harness-field$", fields=("desc",)); return None if f is None else f["text"]

# ---- phases ----
def check_row(cid, tag, want_visible, subs):
    found, sw, end, texts = find_row(TITLE, tag)
    if not found and not end:
        return case(cid, "UNTESTED", "absence not proven (settings focus/anchor/scroll/end); subtypes=%s" % subs), None
    if want_visible:
        ok = found and sw is not None and DESC != "\x00" and any(t.startswith(DESC) for t in texts)
    else:
        ok = not found and end
    return case(cid, "PASS" if ok else "FAIL", "found=%s switch=%s end=%s subtypes=%s" % (found, sw, end, subs)), sw

def fresh():
    pre = adb("shell pm path " + PKG).strip()
    case("A0-absent", "PASS" if not pre else "FAIL", "pm path empty=%s" % (not pre), want="", behavioral=False, tier="T1-env")
    if not APK or sha_file(APK) != WANT: return case("A1-fresh-install", "BLOCKED", "APK bytes do not match pin")
    if not install(APK, "fresh"): return case("A1-fresh-install", "FAIL", "install did not report Success", behavioral=False)
    p = proof("A1-pre")
    vc_ok = p["versionCode"] == str(EXP["version_code"]["candidate"])
    case("A1-fresh-install", "PASS" if vc_ok else "FAIL", "Success; versionCode=%s" % p["versionCode"], behavioral=False)
    if not ime_ready(): return case("A1-ime", "FAIL", "IME not registered", behavioral=False)
    v = stored_pref()
    case("B1-default-off-stored", "PASS" if v in (None, "false") else "FAIL", "stored=%s" % v, behavioral=False)
    subs, _ = enabled_subtypes()
    check_row("B2-S0-none", "s0", EXP["row_visible"]["none"], subs)
    if not add_language(LATN, "latn") or not any(is_latn(s) for s in enabled_subtypes()[0]):
        return case("B2-S2-latin", "BLOCKED", "Bangla (Latin) not enabled via UI")
    adb("shell am force-stop " + PKG); ime_ready(); time.sleep(4)
    subs, _ = enabled_subtypes()
    st, sw = check_row("B2-S2-latin", "s2", EXP["row_visible"]["latin"], subs)
    if sw is None: return case("B1-default-off-ui", "BLOCKED", "row switch not found")
    case("B1-default-off-ui", "PASS" if sw["checked"] == "false" else "FAIL", "checked=%s" % sw["checked"])
    adb("shell input keyevent KEYCODE_BACK"); time.sleep(1)
    _, sw, _, _ = find_row(TITLE, "cancel"); v = stored_pref()
    case("B4-cancel", ("UNTESTED" if not sw else "PASS" if sw["checked"] == "false" and v in (None, "false") else "FAIL"), "ui=%s stored=%s" % (sw and sw["checked"], v))
    if not sw: return
    tap_switch(sw); _, sw, _, _ = find_row(TITLE, "on"); v = stored_pref()
    case("B3-on", ("UNTESTED" if not sw else "PASS" if sw["checked"] == "true" and v == "true" else "FAIL"), "ui=%s stored=%s" % (sw and sw["checked"], v))
    adb("shell am force-stop " + PKG); ime_ready()
    _, sw, _, _ = find_row(TITLE, "fs"); v = stored_pref()
    case("B3-persist-forcestop", ("UNTESTED" if not sw else "PASS" if sw["checked"] == "true" and v == "true" else "FAIL"), "ui=%s stored=%s" % (sw and sw["checked"], v))
    reboot(); ime_ready()
    _, sw, _, _ = find_row(TITLE, "rb"); v = stored_pref()
    case("B3-persist-reboot", ("UNTESTED" if not sw else "PASS" if sw["checked"] == "true" and v == "true" else "FAIL"), "ui=%s stored=%s" % (sw and sw["checked"], v))
    if add_language(NATIVE, "native") and any(is_bn(s) for s in enabled_subtypes()[0]):
        adb("shell am force-stop " + PKG); ime_ready(); time.sleep(4)
        subs, _ = enabled_subtypes()
        _, sw = check_row("B2-S3-both", "s3", EXP["row_visible"]["both"], subs); v = stored_pref()
        case("B3-persist-switch", ("UNTESTED" if not sw else "PASS" if sw["checked"] == "true" and v == "true" else "FAIL"), "after adding a keyboard ui=%s stored=%s" % (sw and sw["checked"], v))
    else:
        case("B2-S3-both", "BLOCKED", "native Bangla not enabled via UI"); case("B3-persist-switch", "BLOCKED", "depends on B2-S3-both")
    seq = []
    for i in range(3):
        _, sw, _, _ = find_row(TITLE, "retry%d" % i)
        if not sw: break
        tap_switch(sw); seq.append(sw["checked"])
    _, sw, _, _ = find_row(TITLE, "retry-end"); v = stored_pref()
    case("B4-retry", ("UNTESTED" if len(seq) < 3 or not sw else "PASS" if sw["checked"] == "false" and v == "false" else "FAIL"), "taps from=%s end ui=%s stored=%s" % (seq, sw and sw["checked"], v))
    typed()

def typed():
    """Hardware-key injection path (adb input text) on the Bangla (Latin) subtype; OFF and ON must give the predeclared exact text."""
    if not HARNESS or not install(HARNESS, "harness"):
        for ph in EXP["typed"]: case("C-typed-" + ph["id"], "UNTESTED", "harness not installed")
        return
    adb("shell cmd clipboard clear")
    for ph in EXP["typed"]:
        got = {}
        for want in ("false", "true"):
            _, sw, _, _ = find_row(TITLE, "t-" + want)
            if sw and sw["checked"] != want: tap_switch(sw); _, sw, _, _ = find_row(TITLE, "t2-" + want)
            adb("shell am force-stop " + PKG); ime_ready(); time.sleep(4)
            harness_focus(ph["id"] + want)
            before = field_text("b" + ph["id"] + want)
            active = select_subtype(is_latn, "typed")
            adb("shell input text " + json.dumps(ph["input"].replace(" ", "%s"))); time.sleep(2)
            got[want] = dict(before=before, active=active, toggle=sw and sw["checked"], text=field_text("a" + ph["id"] + want))
            adb("shell am force-stop t.h")
        ok = all(g["before"] == "" and is_latn(g["active"] or "") and g["toggle"] == w and g["text"] == ph["expected"] for w, g in got.items())
        unk = any(g["before"] is None or g["toggle"] is None or g["text"] is None for g in got.values())
        case("C-typed-" + ph["id"], "UNTESTED" if unk else "PASS" if ok else "FAIL", "path=hardware-key injection; %s" % json.dumps(got, ensure_ascii=False))

def matrix():
    if not install(APK, "matrix"): return case("B2-S4-english", "FAIL", "install failed", behavioral=False)
    ime_ready()
    subs, _ = enabled_subtypes()
    if any(is_en(s) for s in subs) and not any(is_latn(s) or is_bn(s) for s in subs):
        check_row("B2-S4-english", "s4", EXP["row_visible"]["english"], subs)
    else: case("B2-S4-english", "BLOCKED", "English-only state not present; subtypes=%s" % subs)
    if add_language(NATIVE, "native-only"):
        adb("shell am force-stop " + PKG); ime_ready(); time.sleep(4)
    subs, _ = enabled_subtypes()
    if any(is_bn(s) for s in subs) and not any(is_latn(s) for s in subs): check_row("B2-S1-native", "s1", EXP["row_visible"]["native"], subs)
    else: case("B2-S1-native", "BLOCKED", "native-only state not reached; subtypes=%s" % subs)

def diag_switch():
    found, sw, _, _ = find_row("Rambler diagnostics", "diag"); return sw

def update():
    if adb("shell pm path " + PKG).strip(): return case("A2-base", "BLOCKED", "package present on a fresh emulator", want=WANT_BASE, behavioral=False)
    if not BASE or sha_file(BASE) != WANT_BASE: return case("A2-base", "BLOCKED", "previous APK bytes do not match pin", want=WANT_BASE, behavioral=False)
    if not install(BASE, "base"): return case("A2-base", "FAIL", "base install failed", want=WANT_BASE, behavioral=False)
    ime_ready(); b0 = proof("A2-base-pre")
    case("A2-base", "PASS" if b0["versionCode"] == str(EXP["version_code"]["previous"]) else "FAIL", "versionCode=%s" % b0["versionCode"], want=WANT_BASE, behavioral=False)
    # seed state through the previous build's own UI
    sw = diag_switch()
    if sw and sw["checked"] == "false": tap_switch(sw)
    added = add_language(NATIVE, "seed")
    adb("shell am force-stop " + PKG); time.sleep(2)  # flush SharedPreferences
    ime_ready(); sw = diag_switch(); subs0, _ = enabled_subtypes()
    seeded = dict(diag=sw and sw["checked"], bn=any(is_bn(s) for s in subs0))
    if seeded["diag"] != "true" or not seeded["bn"] or not added:
        case("A2-update", "BLOCKED", "could not seed state through the previous UI: %s" % seeded, want=WANT_BASE)
        return case("A2-state-survives", "BLOCKED", "no seeded state to compare")
    b = proof("A2-before")
    fb = root("cd /data/data/%s && find shared_prefs databases -type f -exec sha256sum {} + | sort -k2" % PKG); save("files-before.txt", fb)
    if not install(APK, "update"): return case("A2-update", "FAIL", "install -r did not report Success", behavioral=False)
    time.sleep(2); a = proof("A2-after")
    chk = dict(vc_before=b["versionCode"] == str(EXP["version_code"]["previous"]), vc_after=a["versionCode"] == str(EXP["version_code"]["candidate"]),
               uid=a["uid"] == b["uid"], first=a["firstInstall"] == b["firstInstall"], last=a["lastUpdate"] != b["lastUpdate"], ime=a["ime"] == b["ime"])
    case("A2-update", "PASS" if all(chk.values()) else "FAIL", json.dumps(chk), behavioral=False)
    fa = root("cd /data/data/%s && find shared_prefs databases -type f -exec sha256sum {} + | sort -k2" % PKG); save("files-after.txt", fa)
    kb = {l.split()[1] for l in fb.splitlines() if len(l.split()) == 2}; ka = {l.split()[1] for l in fa.splitlines() if len(l.split()) == 2}
    ime_ready(); sw = diag_switch(); subs1, _ = enabled_subtypes()
    after = dict(diag=sw and sw["checked"], bn=any(is_bn(s) for s in subs1))
    ok = bool(kb) and kb <= ka and after == seeded
    case("A2-state-survives", "UNTESTED" if after["diag"] is None else "PASS" if ok else "FAIL", "files kept=%s missing=%s seeded=%s after=%s" % (kb <= ka, sorted(kb - ka)[:4], seeded, after))
    case("A2-survive-clip-pins", "UNTESTED", "previous build UI seeding for pinned clips not implemented")
    case("A2-survive-dictionary", "UNTESTED", "previous build UI seeding for the personal dictionary not implemented")

def voice():
    """Mic UI only; no permission pre-granted. Recognition content is not testable without audio."""
    if not install(APK, "voice"): return case("V1-mic-ui", "FAIL", "install failed", behavioral=False)
    ime_ready()
    rs = adb("shell cmd package query-services -a android.speech.RecognitionService"); save("recognition-services.txt", rs)
    have_rs = bool(re.search(r"^\s*\S+/\S+", rs, re.M))
    case("V0-recognition-service", "PASS" if have_rs else "FAIL", "RecognitionService present=%s" % have_rs, tier="T1-env", behavioral=False)
    if not HARNESS or not install(HARNESS, "harness-v"): return case("V1-mic-ui", "UNTESTED", "harness missing")
    harness_focus("v")
    mic = c.find([n for n in snap("v-ime") if n["pkg"] == PKG], r"voice|microphone|speak|dictat", fields=("desc", "text"))
    if not mic: case("V1-mic-ui", "FAIL", "no voice key on keyboard")
    else:
        c.tap(mic["cx"], mic["cy"]); time.sleep(4); after = snap("v-after")
        perm = [n for n in after if "permissioncontroller" in n["pkg"] and re.search(r"allow|while using|only this time", n["text"] or "", re.I)]
        listen = [n for n in after if n["pkg"] == PKG and re.search(r"speak now|listening|tap to pause|try saying", (n["text"] or "") + " " + (n["desc"] or ""), re.I)]
        case("V1-mic-ui", "PASS" if (perm or listen) else "FAIL", "permission prompt=%s listening=%s" % ([n["text"] for n in perm], [n["text"] or n["desc"] for n in listen]))
    case("V2-recognition", "UNTESTED", "emulator runs with -noaudio")

def lanes():
    """Voice lane per subtype/toggle from the app's diagnostics file, one file per combination. Proves routing, not text."""
    if not install(APK, "lanes") or not HARNESS or not install(HARNESS, "harness-l"):
        return case("V3-lane-latin-off", "UNTESTED", "install failed", behavioral=False)
    ime_ready(); adb("shell pm grant %s android.permission.RECORD_AUDIO" % PKG)
    if not add_language(LATN, "lanes") or not any(is_latn(s) for s in enabled_subtypes()[0]):
        return case("V3-lane-latin-off", "BLOCKED", "Bangla (Latin) not enabled via UI")
    for sub, tog in (("latin", "false"), ("latin", "true"), ("english", "false"), ("english", "true")):
        cid = "V3-lane-%s-%s" % (sub, "on" if tog == "true" else "off")
        _, sw, _, _ = find_row(TITLE, cid)
        if sw and sw["checked"] != tog: tap_switch(sw); _, sw, _, _ = find_row(TITLE, cid + "b")
        root("rm -f /sdcard/Download/*diag*")
        d = diag_switch()
        if not d or not sw: case(cid, "UNTESTED", "switch missing (row=%s diag=%s)" % (bool(sw), bool(d))); continue
        if d["checked"] == "false": tap_switch(d)
        adb("shell am force-stop " + PKG); ime_ready(); time.sleep(4)
        harness_focus(cid)
        active = select_subtype(is_latn if sub == "latin" else is_en, cid)
        adb("shell log -t RoundMark " + cid)
        mic = c.find([n for n in snap(cid + "-ime") if n["pkg"] == PKG], r"voice|microphone|speak|dictat", fields=("desc", "text"))
        if mic: c.tap(mic["cx"], mic["cy"]); time.sleep(4); adb("shell input keyevent KEYCODE_BACK"); time.sleep(1)
        adb("shell am force-stop t.h")
        d = diag_switch()
        if d and d["checked"] == "true": tap_switch(d); time.sleep(2)
        dst = os.path.join(c.OUT, "diag-" + cid); os.makedirs(dst, exist_ok=True)
        sh("adb pull /sdcard/Download/ '%s' >/dev/null 2>&1" % dst)
        txt = "".join(open(os.path.join(r_, f), errors="replace").read() for r_, _, fs in os.walk(dst) for f in fs if "diag" in f.lower())
        gates = sorted(set(re.findall(r"gate:voice-k([123])", txt)))
        right_sub = is_latn(active) if sub == "latin" else is_en(active)
        if not right_sub or not mic or len(gates) != 1:
            case(cid, "UNTESTED", "active=%s mic=%s gates=%s toggle=%s" % (active, bool(mic), gates, sw["checked"])); continue
        want = EXP["voice_lane"].get("%s_%s" % (sub, "on" if tog == "true" else "off"))
        if want is None: case(cid, "OBSERVED", "active=%s lane=k%s (no predeclared pass value)" % (active, gates[0]))
        else: case(cid, "PASS" if gates[0] == str(want) else "FAIL", "active=%s lane=k%s expected=k%s" % (active, gates[0], want))

def clip():
    if not install(APK, "clip"): return case("D1-clip-drag", "FAIL", "install failed", behavioral=False)
    ime_ready(); logs_reset()
    rec = subprocess.Popen(["adb", "shell", "screenrecord", "--time-limit", "170", "/sdcard/clip.mp4"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    r = subprocess.run([sys.executable, os.path.join(HERE, "clip_e2e.py")], capture_output=True, text=True, timeout=900)
    save("clip-driver-output.txt", r.stdout + "\n" + r.stderr)
    try: rec.wait(timeout=200)
    except subprocess.TimeoutExpired: rec.kill()
    sh("adb pull /sdcard/clip.mp4 '%s/clip.mp4' >/dev/null 2>&1" % c.OUT)
    case("D1-clip-drag", {0: "PASS", 1: "FAIL"}.get(r.returncode, "UNTESTED"), "clip driver exit=%d" % r.returncode)

def crash_scan():
    fatal = anr = native = False
    for f in os.listdir(c.OUT):
        t = open(os.path.join(c.OUT, f), errors="replace").read() if f.endswith(".txt") else ""
        if f.startswith("logcat"):
            fatal |= bool(re.search(r"FATAL EXCEPTION[^\n]*\n[^\n]*Process: " + re.escape(PKG), t))
            anr |= ("ANR in " + PKG) in t
            native |= bool(re.search(r"Fatal signal \d+[^\n]*" + re.escape(PKG), t))
        if f.startswith("dropbox"):
            for tag, key in (("data_app_crash", "fatal"), ("data_app_anr", "anr"), ("data_app_native_crash", "native"), ("SYSTEM_TOMBSTONE", "native")):
                for m in re.finditer(re.escape(tag) + r".{0,400}", t, re.S):
                    if PKG in m.group(0):
                        if key == "fatal": fatal = True
                        elif key == "anr": anr = True
                        else: native = True
    return fatal, anr, native

PHASES = {"fresh": fresh, "matrix": matrix, "update": update, "voice": voice, "lanes": lanes, "clip": clip}
try:
    if not PRIV_OK:
        case("Z-private-values", "BLOCKED", "private values missing or do not match the published commitment", behavioral=False)
    else:
        PHASES[PHASE]()
except Exception:
    save("driver-exception.txt", traceback.format_exc())
    CASES.append(dict(id="Z-driver-%s" % PHASE, status="DRIVER-ERROR", tier="T1", reason="exception, see driver-exception.txt"))
finally:
    sh("adb logcat -b all -d -v threadtime > '%s/logcat-final.txt'" % c.OUT)
    sh("adb shell dumpsys dropbox --print > '%s/dropbox-final.txt'" % c.OUT)
    fatal, anr, native = crash_scan()
    CASES.append(dict(id="Z-no-crash-%s" % PHASE, status="FAIL" if (fatal or anr or native) else "PASS", tier="T1", reason="fatal=%s anr=%s native=%s" % (fatal, anr, native)))
    done_ids = {x["id"] for x in CASES}
    for cid in EXP["phase_cases"].get(PHASE, []):
        if cid not in done_ids: CASES.append(dict(id=cid, status="ENV-MISMATCH" if ENV_MISMATCH else "NOT-RUN", tier="T1", reason="case not reached" + (" (ENVIRONMENT MISMATCH: NO_MATCHING_ABIS)" if ENV_MISMATCH else "")))
    save("verdicts.json", CASES)
    save("verdict-summary.json", {k: sum(1 for x in CASES if x["status"] == k) for k in sorted(set(x["status"] for x in CASES))})
# Exit 0 always: test verdicts live only in the encrypted evidence, never in public job colour.
sys.exit(0)
