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
ROOT = {"ok": None, "why": ""}
UNREADABLE = "UNREADABLE"

def run_fast(argv, timeout):
    """Runs a command with stdin closed and a hard timeout; never raises, never hangs."""
    try:
        r = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -2, "", repr(e)

def root_setup():
    """adb root once per phase, then prove the adb shell is uid 0. No su is used anywhere."""
    rc, out, err = run_fast(["adb", "root"], 30)
    run_fast(["adb", "wait-for-device"], 120)
    time.sleep(3)
    rc2, uid, err2 = run_fast(["adb", "shell", "id", "-u"], 15)
    ROOT["ok"] = rc2 == 0 and uid.strip() == "0"
    ROOT["why"] = "adb root rc=%s out=%r; id -u=%r" % (rc, (out + err).strip()[:120], uid.strip()[:20])
    save("root-setup.json", ROOT)
    return ROOT["ok"]

def root(cmd, timeout=30):
    """Root-only read. Returns UNREADABLE (never hangs) when root was not proven or the command times out."""
    if not ROOT["ok"]: return UNREADABLE
    rc, out, err = run_fast(["adb", "shell", cmd], timeout)
    return out if rc == 0 else UNREADABLE
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

OPEN_N = [0]

def open_settings(tag):
    run_fast(["adb", "shell", "am", "start", "-W", "-n", ACT], 30); time.sleep(3)
    OPEN_N[0] += 1; n = OPEN_N[0]
    # raw, unfiltered evidence for every settings open (no parsing, no filtering)
    rc, out, err = run_fast(["adb", "logcat", "-b", "all", "-d", "-v", "threadtime", "-t", "4000"], 60)  # last 4000 raw lines, unfiltered
    save("open-%02d-%s-logcat.txt" % (n, tag), out if rc == 0 else "LOGCAT-FAILED rc=%s %s" % (rc, err[:200]))
    rc, out, err = run_fast(["adb", "shell", "dumpsys", "input_method"], 30)
    save("open-%02d-%s-dumpsys-input_method.txt" % (n, tag), out if rc == 0 else "DUMPSYS-FAILED rc=%s %s" % (rc, err[:200]))

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

TAP_N = [0]

def switch_at(cx, cy):
    """Checked state of the checkable node whose bounds contain (cx, cy) on a fresh snapshot."""
    t = tree()
    if t is None: return None
    for n in t.iter("node"):
        b = bounds(n)
        if n.get("checkable") == "true" and b and b[0] <= cx <= b[2] and b[1] <= cy <= b[3]:
            return n.get("checked")
    return None

def tap_switch(sw):
    c.tap(sw["cx"], sw["cy"]); time.sleep(1.5)
    TAP_N[0] += 1; n = TAP_N[0]
    snap("tap-%02d-after" % n)
    after = switch_at(sw["cx"], sw["cy"])
    save("tap-%02d.json" % n, dict(t=time.time(), cx=sw["cx"], cy=sw["cy"], res=sw.get("res"),
                                    before=sw.get("checked"), after=after))
    return after

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
    rc, hout, _ = run_fast(["adb", "shell", "sha256sum", base[0]], 60) if base else (1, "", "")
    bsha = hout.split()[0] if rc == 0 and hout.split() else ""
    dp = adb("shell dumpsys package " + PKG)
    g = lambda rx: (re.search(rx, dp).group(1).strip() if re.search(rx, dp) else "")
    flags = g(r"pkgFlags=\[([^\]]*)\]") + " " + g(r"privateFlags=\[([^\]]*)\]")
    pid = adb("shell pidof " + PKG).strip()
    mapped = root("grep -m1 -o '/data/app/[^ ]*base.apk' /proc/%s/maps" % pid).strip() if pid else ""
    maps_readable = mapped != UNREADABLE
    p = dict(case=cid, t=time.time(), paths=paths, base_sha256=bsha, split=len(paths) > 1,
             versionCode=g(r"versionCode=(\d+)"), firstInstall=g(r"firstInstallTime=([^\n]+)"),
             lastUpdate=g(r"lastUpdateTime=([^\n]+)"), uid=g(r"userId=(\d+)"), sharedUser=("sharedUser=" in dp),
             debuggable=("DEBUGGABLE" in flags), testOnly=("TEST_ONLY" in flags),
             instrumentation=(PKG in adb("shell pm list instrumentation")), pid=pid,
             pid_maps_base=(bool(base) and mapped == base[0]) if maps_readable else None, root_ok=ROOT["ok"],
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
    if status == "FAIL" and UNREADABLE in reason:
        status, reason = "UNTESTED", "root-only read unavailable (%s): %s" % (ROOT["why"], reason)
    if ENV_MISMATCH and status in ("FAIL", "UNTESTED", "BLOCKED"):
        status, reason = "ENV-MISMATCH", "ENVIRONMENT MISMATCH (no arm64 support on this emulator, NO_MATCHING_ABIS at %s); not a product result. %s" % (ENV_MISMATCH, reason)
    if status == "PASS" and tier == "T1" and not grounded(p, WANT if want is None else want, behavioral):
        why = "root unavailable, pid map unreadable" if behavioral and p["pid_maps_base"] is None else "hash/split/flags/pid map"
        status, reason = "BLOCKED", "grounding failed (%s): %s" % (why, reason)
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
    """Returns 'true'/'false' when stored, None when root is proven and no prefs file holds the key (default),
    UNREADABLE only when root is not proven or the read itself fails."""
    ts = int(time.time() * 1000)
    if ROOT["ok"]:
        rc, out, err = run_fast(["adb", "shell", "ls", "-1", PREFS], 20)
        xmls = [l for l in out.split() if l.endswith(".xml")] if rc == 0 else []
        if rc != 0 and ("No such file" in out + err or "No such file" in err):
            save("prefs-%d.txt" % ts, "ABSENT (no shared_prefs dir; root proven)"); return None
        if rc == 0 and not xmls:
            save("prefs-%d.txt" % ts, "ABSENT (shared_prefs has no xml; root proven)"); return None
    t = root("cat %s/*.xml" % PREFS); save("prefs-%d.txt" % ts, t)
    if t == UNREADABLE: return UNREADABLE
    m = re.search(r'<boolean name="%s" value="(true|false)"' % re.escape(KEY), t); return m.group(1) if m else None

def add_language(pattern, label):
    # The launcher resumes the task on its last screen (round 2: "Advanced settings"), so clear the task first,
    # then launch fresh; fall back to backing out if "Languages" is still not reachable.
    run_fast(["adb", "shell", "am", "start", "-W", "--activity-clear-task", "-a", "android.intent.action.MAIN",
              "-c", "android.intent.category.LAUNCHER", "-f", "0x10008000", "-p", PKG], 30); time.sleep(4)
    for _ in range(4):
        if c.find(snap("root-" + label), r"^(languages|done)$", fields=("text",)): break
        adb("shell input keyevent KEYCODE_BACK"); time.sleep(1.5)
    else:
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

def cert_digests(path):
    """Signer certificate SHA-256 digests of an APK via apksigner from the runner's Android SDK; [] when unavailable."""
    if not path or not os.path.exists(path): return []
    import glob
    roots = [os.environ.get(k, "") for k in ("ANDROID_HOME", "ANDROID_SDK_ROOT")]
    tools = sorted(t for r in roots if r for t in glob.glob(os.path.join(r, "build-tools", "*", "apksigner")))
    if not tools: return []
    rc, out, err = run_fast([tools[-1], "verify", "--print-certs", path], 120)
    return sorted(set(re.findall(r"certificate SHA-256 digest: ([0-9a-f]{64})", out))) if rc == 0 else []

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
    sig = lambda: (re.search(r"signatures:\[([^\]]*)\]", adb("shell dumpsys package " + PKG)) or re.search(r"(?!)", ""))
    sb = sig(); sb = sb.group(1) if sb else ""
    certs = dict(base=cert_digests(BASE), candidate=cert_digests(APK)); save("a2-signer-certs.json", certs)
    if not certs["base"] or certs["base"] != certs["candidate"]:
        case("A2-update", "BLOCKED", "setup: signer certificates of the pinned files not verified equal %s" % certs, behavioral=False)
        return case("A2-state-survives", "BLOCKED", "no verified same-signer replacement")
    fb = root("cd /data/data/%s && find shared_prefs databases -type f -exec sha256sum {} + | sort -k2" % PKG); save("files-before.txt", fb)
    if not install(APK, "update"):
        io = open(os.path.join(c.OUT, "install-update.txt"), errors="replace").read()
        if "UPDATE_INCOMPATIBLE" in io: return case("A2-update", "BLOCKED", "setup: INSTALL_FAILED_UPDATE_INCOMPATIBLE (signer mismatch)", behavioral=False)
        return case("A2-update", "FAIL", "install -r did not report Success", behavioral=False)
    time.sleep(2); a = proof("A2-after")
    sa = sig(); sa = sa.group(1) if sa else ""
    chk = dict(vc_before=b["versionCode"] == str(EXP["version_code"]["previous"]), vc_after=a["versionCode"] == str(EXP["version_code"]["candidate"]),
               uid=a["uid"] == b["uid"], first=a["firstInstall"] == b["firstInstall"], last=a["lastUpdate"] != b["lastUpdate"], ime=a["ime"] == b["ime"],
               pins_differ=bool(WANT) and bool(WANT_BASE) and WANT != WANT_BASE,
               installed_before_is_base=b["base_sha256"] == WANT_BASE, installed_after_is_candidate=a["base_sha256"] == WANT)
    save("a2-dumpsys-signatures.json", dict(before=sb, after=sa))  # evidence only
    case("A2-update", "PASS" if all(chk.values()) else "FAIL", json.dumps(chk), behavioral=False)
    fa = root("cd /data/data/%s && find shared_prefs databases -type f -exec sha256sum {} + | sort -k2" % PKG); save("files-after.txt", fa)
    kb = {l.split()[1] for l in fb.splitlines() if len(l.split()) == 2}; ka = {l.split()[1] for l in fa.splitlines() if len(l.split()) == 2}
    ime_ready(); sw = diag_switch(); subs1, _ = enabled_subtypes()
    after = dict(diag=sw and sw["checked"], bn=any(is_bn(s) for s in subs1))
    ok = bool(kb) and kb <= ka and after == seeded
    case("A2-state-survives", "UNTESTED" if (after["diag"] is None or UNREADABLE in (fb, fa)) else "PASS" if ok else "FAIL", "files kept=%s missing=%s seeded=%s after=%s" % (kb <= ka, sorted(kb - ka)[:4], seeded, after))
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

GATE_LOG = {}
ENBN = re.compile(r"enbn-gate t=(\d+) (yes|no) (settings|voice) tog=(on|off)")
# Voice-launch lane line from the product: "HH:mm:ss.SSS subtype locale=<l> extras=<e> tag=<t> hash=<h> -> k<N>" (post-adjust lane).
# It is written when Gboard builds the dictation request (mic tap), so it exists without audio. "gate:voice-k3" only appears
# when recognized text is processed, which never happens on a -noaudio emulator; it is kept as evidence only.
SUBK = re.compile(r"(\d\d):(\d\d):(\d\d)\.(\d\d\d) subtype locale=(\S*) extras=.*? tag=(\S*) hash=(-?\d+) -> k([123])\b")

MARK_FALLBACK = [False]

def dev_now():
    """Device clock: epoch ms and ms since local midnight (the diagnostics log stamps HH:mm:ss.SSS).
    Falls back to whole seconds (marker rounded down, never later than the true time) when the device date lacks %N."""
    rc, out, _ = run_fast(["adb", "shell", "date +%s%3N' '%H:%M:%S.%3N"], 15)
    try:
        ms, tod = out.split(); h, m, rest = tod.split(":"); sec, milli = rest.split(".")
        return int(ms), ((int(h) * 60 + int(m)) * 60 + int(sec)) * 1000 + int(milli)
    except Exception:
        pass
    MARK_FALLBACK[0] = True
    rc, out, _ = run_fast(["adb", "shell", "date +%s' '%H:%M:%S"], 15)
    try:
        s_, tod = out.split(); h, m, sec = tod.split(":")
        return int(s_) * 1000, ((int(h) * 60 + int(m)) * 60 + int(sec)) * 1000
    except Exception:
        return None, None

def diag_files():
    """(name, mtime_s) of diagnostics files in Download, or None when the listing itself fails."""
    rc, out, err = run_fast(["adb", "shell", "for f in /sdcard/Download/*; do [ -f \"$f\" ] && stat -c '%Y %n' \"$f\"; done; echo END"], 20)
    if rc != 0 or not out.strip().endswith("END"): return None
    r = []
    for l in out.splitlines():
        p = l.split(" ", 1)
        if len(p) == 2 and p[0].isdigit() and "diag" in p[1].lower(): r.append((p[1], int(p[0])))
    return r

def set_switch(finder, want, tag):
    """Set a switch and prove it from a fresh snapshot. Returns (row_switch_or_None, verified_bool)."""
    sw = finder(tag)
    if not sw: return None, False
    if sw["checked"] != want:
        after = tap_switch(sw)
        sw = finder(tag + "-re")
        if not sw or after != want: return sw, False
    return sw, sw["checked"] == want

def gate_log_case():
    """V3-gate-log from the current, provenance-proven voice decisions only."""
    spec = EXP.get("gate_log") or {}
    save("gate-log.json", GATE_LOG)
    need, off = list(spec.get("cases", [])), list(spec.get("off_cases", []))
    if not need: return case("V3-gate-log", "UNTESTED", "no gate_log cases declared")
    per = {}
    for cid in need:
        g = GATE_LOG.get(cid)
        if g is None: per[cid] = "UNTESTED: lane not reached"
        elif not g["pre_ok"]: per[cid] = "BLOCKED: preconditions %s" % g["pre"]
        elif not g["prov_ok"]: per[cid] = "UNTESTED: provenance %s" % g["prov"]
        elif not g["active_snapshot"]["ok"]: per[cid] = "UNTESTED: active subtype snapshot invalid %s" % g["active_snapshot"]
        elif g["subtype_mismatched"]: per[cid] = "UNTESTED: current voice-launch lines not bound to the active subtype %s" % [(r["locale"], r["tag"], r["hash"], "k" + r["k"]) for r in g["subtype_mismatched"]][:3]
        elif not g["lanes"]: per[cid] = "UNTESTED: no current voice-launch line bound to the active subtype"
        elif any(x["kind"] == "voice" for x in g["malformed"]): per[cid] = "FAIL: current malformed caller=voice line %s" % [x["raw"] for x in g["malformed"] if x["kind"] == "voice"][:3]
        elif any(x["kind"] in ("undatable", "no-caller") for x in g["malformed"]): per[cid] = "UNTESTED: undatable or caller-less enbn-gate line %s" % [x["raw"] for x in g["malformed"] if x["kind"] in ("undatable", "no-caller")][:3]
        elif not g["voice"]: per[cid] = "UNTESTED: no current voice gate line"
        elif any(l["res"] != "yes" or l["tog"] != "on" or l["err"] for l in g["voice"]): per[cid] = "FAIL: current no/error/toggle-off line %s" % [l["raw"] for l in g["voice"] if l["res"] != "yes" or l["tog"] != "on" or l["err"]][:3]
        else: per[cid] = "PASS"
    for cid in off:
        g = GATE_LOG.get(cid)
        if not g: per[cid] = "UNTESTED: negative control not reached"
        elif not g["pre_ok"]: per[cid] = "BLOCKED: negative control preconditions %s" % g["pre"]
        elif not g["prov_ok"]: per[cid] = "UNTESTED: negative control provenance %s" % g["prov"]
        elif not g["active_snapshot"]["ok"]: per[cid] = "UNTESTED: active subtype snapshot invalid %s" % g["active_snapshot"]
        elif g["subtype_mismatched"]: per[cid] = "UNTESTED: current voice-launch lines not bound to the active subtype %s" % [(r["locale"], r["tag"], r["hash"], "k" + r["k"]) for r in g["subtype_mismatched"]][:3]
        elif not g["lanes"]: per[cid] = "UNTESTED: no current voice-launch line bound to the active subtype, so absence proves nothing"
        elif any(x["kind"] == "voice" for x in g["malformed"]): per[cid] = "FAIL: current malformed caller=voice line %s" % [x["raw"] for x in g["malformed"] if x["kind"] == "voice"][:3]
        elif any(x["kind"] in ("undatable", "no-caller") for x in g["malformed"]): per[cid] = "UNTESTED: undatable or caller-less enbn-gate line"
        elif g["voice"]: per[cid] = "FAIL: voice gate ran with the toggle proven off in the UI %s" % [l["raw"] for l in g["voice"]][:3]
        else: per[cid] = "PASS: no current voice gate line with the toggle off"
    st = [v.split(":")[0] for v in per.values() if not v.startswith("N/A")]
    if not any(v == "PASS" for k, v in per.items() if k in need): st.append("UNTESTED")
    status = "FAIL" if "FAIL" in st else "BLOCKED" if "BLOCKED" in st else "UNTESTED" if "UNTESTED" in st else "PASS"
    case("V3-gate-log", status, json.dumps(per, ensure_ascii=False))

def lanes():
    try:
        lanes_inner()
    finally:
        gate_log_case()

def lanes_inner():
    """Voice lane per subtype/toggle from the app's diagnostics file, one new file per combination, bound to a device-time
    marker. Proves routing, not text. Only lines stamped after the marker, in files created after it, are graded."""
    if not install(APK, "lanes") or not HARNESS or not install(HARNESS, "harness-l"):
        return case("V3-lane-latin-off", "UNTESTED", "install failed", behavioral=False)
    ime_ready(); adb("shell pm grant %s android.permission.RECORD_AUDIO" % PKG)
    if not add_language(LATN, "lanes") or not any(is_latn(s) for s in enabled_subtypes()[0]):
        return case("V3-lane-latin-off", "BLOCKED", "Bangla (Latin) not enabled via UI")
    row_finder = lambda tag: find_row(TITLE, tag)[1]
    diag_finder = lambda tag: find_row("Rambler diagnostics", tag)[1]
    for sub, tog in (("latin", "false"), ("latin", "true"), ("english", "false"), ("english", "true")):
        cid = "V3-lane-%s-%s" % (sub, "on" if tog == "true" else "off")
        pre, prov = {}, {}
        _, pre["row_toggle"] = set_switch(row_finder, tog, cid)
        run_fast(["adb", "shell", "rm -f /sdcard/Download/*diag* /sdcard/Download/*Diag* /sdcard/Download/*DIAG*"], 20)
        left = diag_files(); prov["cleared"] = left == []
        _, pre["diag_on"] = set_switch(diag_finder, "true", cid + "-diag")
        adb("shell am force-stop " + PKG); ime_ready(); time.sleep(4)
        pt = root("cat %s/*.xml" % PREFS); save("prefs-%s-armed.txt" % cid, pt)
        pb = lambda k: (re.search(r'<boolean name="%s" value="(true|false)"' % re.escape(k), pt).group(1) if pt != UNREADABLE and re.search(r'<boolean name="%s" value="(true|false)"' % re.escape(k), pt) else ("false" if pt != UNREADABLE else None))
        pre["diag_armed_stored"] = pb("pref_rambler_diag_armed") == "true"
        pre["row_toggle_stored"] = pb(KEY) == tog
        harness_focus(cid)
        active = select_subtype(is_latn if sub == "latin" else is_en, cid)
        pre["subtype"] = bool(is_latn(active) if sub == "latin" else (is_en(active) and not is_latn(active)))
        # rev15: snapshot the active subtype (hash + locale) right before the mic tap; lane lines are bound to it
        act_hash = adb("shell settings get secure selected_input_method_subtype").strip()
        act_loc = enabled_subtypes()[1].get(act_hash, "")
        # rev16: the lane's required subtype class is part of the binding (latin lane: Bangla (Latin); english lane: en, not Latn)
        req = (lambda l: is_latn(l)) if sub == "latin" else (lambda l: is_en(l) and not is_latn(l))
        act_ok = bool(re.fullmatch(r"-?\d+", act_hash)) and act_hash != "-1" and bool(act_loc) and act_loc == active and req(act_loc)
        mark_ms, mark_tod = dev_now(); prov["marker"] = mark_ms is not None
        adb("shell log -t RoundMark '%s t=%s'" % (cid, mark_ms))
        mic = c.find([n for n in snap(cid + "-ime") if n["pkg"] == PKG], r"voice|microphone|speak|dictat", fields=("desc", "text"))
        pre["mic"] = bool(mic)
        if mic: c.tap(mic["cx"], mic["cy"]); time.sleep(4); adb("shell input keyevent KEYCODE_BACK"); time.sleep(1)
        adb("shell am force-stop t.h")
        _, prov["diag_off"] = set_switch(diag_finder, "false", cid + "-diagoff")
        time.sleep(2)
        files = diag_files() or []
        fresh = [f for f, m in files if mark_ms is not None and m >= mark_ms // 1000]
        prov["files"] = [(f, m) for f, m in files]; prov["fresh"] = fresh
        dst = os.path.join(c.OUT, "diag-" + cid); os.makedirs(dst, exist_ok=True)
        txt = ""
        for f in fresh:
            local = os.path.join(dst, os.path.basename(f))
            if run_fast(["adb", "pull", f, local], 60)[0] == 0: txt += open(local, errors="replace").read() + "\n"
        prov_ok = prov["cleared"] and prov["marker"] and prov["diag_off"] and len(fresh) >= 1 and bool(txt.strip())
        # current lines only: gate:voice-kN by time of day, enbn lines by epoch ms, both at or after the marker
        prov["tz"] = adb("shell getprop persist.sys.timezone").strip()
        prov["not_near_midnight"] = mark_tod is not None and mark_tod < 86400000 - 3600000
        prov["ms_marker"] = not MARK_FALLBACK[0]
        prov_ok = prov_ok and prov["not_near_midnight"] and prov["ms_marker"]
        gates, subk, stale, mismatched = [], [], 0, []
        norm = lambda v: (v or "").lower().replace("-", "_")
        for m in SUBK.finditer(txt):
            tod = ((int(m.group(1)) * 60 + int(m.group(2))) * 60 + int(m.group(3))) * 1000 + int(m.group(4))
            if not (mark_tod is not None and 0 <= tod - mark_tod < 3600000): stale += 1; continue
            rec = dict(tod=tod, locale=m.group(5), tag=m.group(6), hash=m.group(7), k=m.group(8), raw=m.group(0)[:300])
            # bound = same subtype hash as the active snapshot AND locale or tag names the active locale
            rec["bound"] = act_ok and rec["hash"] == act_hash and norm(act_loc) in (norm(rec["locale"]), norm(rec["tag"])) and (req(rec["locale"]) or req(rec["tag"]))
            subk.append(rec)
            if rec["bound"]: gates.append(rec["k"])
            else: mismatched.append(rec)
        text_gates = re.findall(r"gate:voice-k([123])", txt)
        voice, other, malformed = [], [], []
        for l in txt.splitlines():
            if "enbn-gate" not in l: continue
            tm = re.search(r"enbn-gate t=(\d+)", l)
            if tm and int(tm.group(1)) < (mark_ms or 0): stale += 1; continue
            m = ENBN.search(l)
            if not m:
                cm = re.search(r"\b(settings|voice)\b", l)
                kind = "undatable" if not tm else "voice" if cm and cm.group(1) == "voice" else "settings" if cm else "no-caller"
                malformed.append(dict(kind=kind, raw=l.strip()[:300])); continue
            rec = dict(t=int(m.group(1)), res=m.group(2), caller=m.group(3), tog=m.group(4), raw=l.strip()[:420],
                       err=bool(re.search(r"\b(app|imm|list|own|hash|secure)-err\b", l)))
            (voice if rec["caller"] == "voice" else other).append(rec)
        prefs = [l.strip()[:300] for l in txt.splitlines() if "enbn-pref t=" in l]
        pre_ok = all(pre.values())
        GATE_LOG[cid] = dict(pre=pre, pre_ok=pre_ok, prov=prov, prov_ok=prov_ok, voice=voice, settings=other, pref=prefs, malformed=malformed,
                             subtype_lines=subk, subtype_mismatched=mismatched, active_snapshot=dict(hash=act_hash, locale=act_loc, ok=act_ok),
                             text_gates_evidence_only=text_gates,
                             lanes=gates, stale_ignored=stale, mark_ms=mark_ms, active=active)
        gset = sorted(set(gates))
        if not pre_ok:
            case(cid, "BLOCKED", "preconditions not proven %s active=%s" % (pre, active)); continue
        if not prov_ok:
            case(cid, "UNTESTED", "diagnostics provenance not proven %s" % prov); continue
        if not act_ok:
            case(cid, "UNTESTED", "active subtype snapshot unavailable or inconsistent hash=%s locale=%s selected=%s" % (act_hash, act_loc, active)); continue
        if mismatched:
            case(cid, "UNTESTED", "current lane lines not bound to the active subtype (hash=%s locale=%s): %s" % (act_hash, act_loc, [(r["locale"], r["tag"], r["hash"], "k" + r["k"]) for r in mismatched][:4])); continue
        if len(gset) != 1:
            case(cid, "UNTESTED", "current lanes=%s (need exactly one) stale_ignored=%d" % (gset, stale)); continue
        want = EXP["voice_lane"].get("%s_%s" % (sub, "on" if tog == "true" else "off"))
        if want is None: case(cid, "OBSERVED", "active=%s lane=k%s (no predeclared pass value)" % (active, gset[0]))
        else: case(cid, "PASS" if gset[0] == str(want) else "FAIL", "active=%s hash=%s lane=k%s expected=k%s bound_lines=%d stale_ignored=%d" % (active, act_hash, gset[0], want, len(gates), stale))

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
        root_setup()
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
