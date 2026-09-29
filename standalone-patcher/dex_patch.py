#!/usr/bin/env python3
"""
dex_patch.py - fail-closed, fingerprint-guarded smali patcher for the
Rambler Bangla - guarded Gboard Rambler Lite Bengali script patch.

GPL-3.0. Derived work of PixelBoard (https://github.com/Akshayykadam/PixelBoard).

This is the reproducible local route used while the credentialed Morphe Gradle
plugin cannot resolve. It never edits bytes blindly: it disassembles the target
DEX with baksmali, verifies exact method anchors and SHA-256 string
fingerprints from a profile, derives the enabled-languages register by local
dataflow on the disassembly, inserts two runtime-hook calls in smali, and
reassembles. Any anchor or fingerprint mismatch aborts with no output.

Requires: a JDK on PATH (or JAVA_HOME), baksmali + smali fat jars.
No Google binaries are included in this repository; the user supplies a
lawfully obtained Gboard APK.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

EXT_DEFAULT = ("Lcom/akshaykadam/pixelboard/extension/ramblerlite/"
               "GboardRamblerLiteScriptRuntime;")
RULE_HOOK = "selectHinglishOverrideRule"
PROMPT_HOOK = "rewriteCleanupPromptScriptGate"
STRING_REPLACE = ("Ljava/lang/String;->replace(Ljava/lang/CharSequence;"
                  "Ljava/lang/CharSequence;)Ljava/lang/String;")


class PatchError(Exception):
    pass


# ---------------------------------------------------------------- smali utils

def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise PatchError("command failed: %s\n%s%s" % (
            " ".join(cmd), proc.stdout, proc.stderr))
    return proc.stdout


def java_cmd():
    home = os.environ.get("JAVA_HOME")
    return os.path.join(home, "bin", "java") if home else "java"


def smali_prefix(kind, jar):
    """Command prefix for smali/baksmali: fat classpath via SMALI_CP if set,
    else a main-class classpath of the two thin jars is NOT assumed; fall back
    to -jar with the given jar (works for the official fat jars)."""
    cp = os.environ.get("SMALI_CP")
    main = "org.jf.baksmali.Main" if kind == "baksmali" else "org.jf.smali.Main"
    if cp:
        return [java_cmd(), "-cp", cp, main]
    return [java_cmd(), "-jar", jar]


def smali_class_path(class_type):
    """Lcom/foo/Bar; -> com/foo/Bar.smali ; Lkfd; -> kfd.smali"""
    return class_type.strip()[1:-1] + ".smali"


def smali_unescape(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        i += 1
        if i >= len(s):
            raise PatchError("trailing backslash in smali string")
        e = s[i]
        i += 1
        table = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f",
                 "\\": "\\", '"': '"', "'": "'"}
        if e == "u":
            out.append(chr(int(s[i:i + 4], 16)))
            i += 4
        elif e in table:
            out.append(table[e])
        else:
            raise PatchError("unsupported smali escape: \\%s" % e)
    return "".join(out)


CONST_RE = re.compile(
    r'^(?P<indent>\s*)const-string(?:/jumbo)?\s+(?P<reg>[vp]\d+),\s*"(?P<body>(?:[^"\\]|\\.)*)"\s*$')


def parse_const_string(line):
    m = CONST_RE.match(line)
    if not m:
        return None
    return m.group("reg"), smali_unescape(m.group("body"))


INVOKE_RE = re.compile(
    r'^\s*invoke-\w+(?:/range)?\s*\{(?P<regs>[^}]*)\},\s*(?P<ref>\S+)\s*$')


def parse_invoke(line):
    m = INVOKE_RE.match(line)
    if not m:
        return None
    regs = [r.strip() for r in m.group("regs").split(",") if r.strip()]
    if ".." in m.group("regs"):
        base, last = [r.strip() for r in m.group("regs").split("..")]
        n0, n1 = int(base[1:]), int(last[1:])
        regs = ["v%d" % n for n in range(n0, n1 + 1)]
    return regs, m.group("ref")


def sha256_text(s):
    # Baksmali may emit unpaired UTF-16 surrogates in unrelated DEX literals.
    # Preserve those code units while scanning; ordinary UTF-8 fingerprints
    # (including the guarded prompt/rule) hash exactly as before.
    return hashlib.sha256(s.encode("utf-8", "surrogatepass")).hexdigest()


def method_bounds(lines, name, proto):
    start = None
    for i, line in enumerate(lines):
        if line.startswith(".method"):
            sig = line.split(None, 1)[1].strip()
            if sig.endswith(name + proto):
                if start is not None:
                    raise PatchError("duplicate method %s%s" % (name, proto))
                start = i
        elif start is not None and line.strip() == ".end method":
            return start, i
    raise PatchError("method %s%s not found" % (name, proto))


def param_slots(proto, is_static):
    params = proto[1:proto.index(")")]
    slots = 0 if is_static else 1
    i = 0
    while i < len(params):
        c = params[i]
        if c == "L":
            i = params.index(";", i) + 1
            slots += 1
        elif c == "[":
            i += 1
        elif c in "JD":
            slots += 2
            i += 1
        else:
            slots += 1
            i += 1
    return slots


def bump_locals(lines, mstart, extra, proto, is_static):
    """Raise the method's local register window; returns first temp vN."""
    for i in range(mstart, len(lines)):
        s = lines[i].strip()
        if s.startswith(".locals"):
            n = int(s.split()[1])
            lines[i] = lines[i].replace(".locals %d" % n, ".locals %d" % (n + extra))
            return n
        if s.startswith(".registers"):
            n = int(s.split()[1])
            locals_n = n - param_slots(proto, is_static)
            lines[i] = lines[i][:len(lines[i]) - len(lines[i].lstrip())] \
                + ".locals %d" % (locals_n + extra)
            return locals_n
        if s.startswith(".end method"):
            break
    raise PatchError("no .locals/.registers in method")


# ------------------------------------------------------------------ profiling

class Profile:
    def __init__(self, path):
        with open(path, encoding="utf-8") as fh:
            self.raw = json.load(fh)
        self.methods = self.raw["methods"]
        self.fingerprints = self.raw["fingerprints"]
        self.anchors = self.raw["anchors"]
        self.ext_class = self.raw.get("extension_class", EXT_DEFAULT)

    def method(self, key):
        m = self.methods[key]
        return m["class"], m["name"], m["signature"]


# ------------------------------------------------------------------- analysis

def disassemble_all(apk, workdir, baksmali_jar):
    dexes = []
    with zipfile.ZipFile(apk) as zf:
        names = [n for n in zf.namelist()
                 if re.fullmatch(r"classes(\d*)\.dex", n)]
        names.sort(key=lambda n: (len(n), n))
        for name in names:
            out = os.path.join(workdir, name.replace(".dex", ""))
            data = zf.read(name)
            tmp = os.path.join(workdir, name)
            with open(tmp, "wb") as fh:
                fh.write(data)
            run(smali_prefix("baksmali", baksmali_jar) + ["d", tmp, "-o", out])
            dexes.append((name, out))
    if not dexes:
        raise PatchError("no classes*.dex entries in %s" % apk)
    return dexes


def scan_fingerprints(dexes, fingerprints):
    """Locate every const-string whose sha256 matches a known fingerprint."""
    hits = {k: [] for k in fingerprints}
    for dex_name, ddir in dexes:
        for root, _dirs, files in os.walk(ddir):
            for fn in files:
                if not fn.endswith(".smali"):
                    continue
                path = os.path.join(root, fn)
                with open(path, encoding="utf-8") as fh:
                    lines = fh.read().splitlines()
                mstart = None
                msig = None
                for idx, line in enumerate(lines):
                    if line.startswith(".method"):
                        mstart = idx
                        msig = line.split(None, 1)[1].strip()
                    elif line.strip() == ".end method":
                        mstart = None
                    parsed = parse_const_string(line)
                    if not parsed:
                        continue
                    _reg, value = parsed
                    digest = sha256_text(value)
                    for key, fp in fingerprints.items():
                        if digest == fp["sha256"]:
                            hits[key].append({
                                "dex": dex_name, "file": path, "line": idx + 1,
                                "method": msig, "method_line": mstart,
                            })
    return hits


def analyze(apk, profile, workdir, baksmali_jar):
    dexes = disassemble_all(apk, workdir, baksmali_jar)
    hits = scan_fingerprints(dexes, profile.fingerprints)
    report = {"apk": apk, "dexes": [d for d, _ in dexes],
              "fingerprint_hits": hits, "methods": {}}
    for key in profile.methods:
        cls, name, proto = profile.method(key)
        found = None
        for dex_name, ddir in dexes:
            path = os.path.join(ddir, smali_class_path(cls))
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            try:
                start, end = method_bounds(lines, name, proto)
            except PatchError:
                continue
            consts = []
            for i in range(start, end + 1):
                p = parse_const_string(lines[i])
                if p:
                    consts.append({"line": i + 1, "reg": p[0],
                                   "sha256": sha256_text(p[1]),
                                   "preview": p[1][:60]})
            found = {"dex": dex_name, "file": path,
                     "lines": [start + 1, end + 1], "const_strings": consts}
            break
        report["methods"][key] = found or {"error": "not found"}
    return report


# ------------------------------------------------------------------- patching

def find_enabled_languages_site(lines, mstart, mend, placeholder):
    """Locate .replace("{ENABLED_LANGUAGES}", langs); returns (langs_reg,
    result_reg, insert_after_index)."""
    const_idx = None
    const_reg = None
    for i in range(mstart, mend + 1):
        p = parse_const_string(lines[i])
        if p and p[1] == placeholder:
            const_idx, const_reg = i, p[0]
            break
    if const_idx is None:
        raise PatchError("placeholder const-string %r not found in method" % placeholder)
    for i in range(const_idx + 1, mend + 1):
        inv = parse_invoke(lines[i])
        if not inv:
            continue
        regs, ref = inv
        if ref == STRING_REPLACE and len(regs) == 3 and regs[1] == const_reg:
            langs_reg = regs[2]
            for j in range(i + 1, mend + 1):
                line = lines[j].strip()
                # Baksmali can place any number of debug directives between
                # invoke and its immediate-result opcode. Do not cross code.
                if not line or line.startswith("#") or line.startswith((
                        ".line ", ".local ", ".end local ",
                        ".restart local ", ".prologue", ".epilogue")):
                    continue
                m = re.fullmatch(r"move-result-object\s+([vp]\d+)", line)
                if m:
                    return langs_reg, m.group(1), j
                break
            raise PatchError("no move-result-object after String.replace")
    raise PatchError("no String.replace using %s after placeholder load" % const_reg)


def hook_snippet(temp0, src_reg, langs_reg, ext, hook):
    return [
        "    move-object/from16 %s, %s" % (temp0, src_reg),
        "    move-object/from16 %s, %s" % ("v%d" % (int(temp0[1:]) + 1), langs_reg),
        "    invoke-static/range {%s .. %s}, %s->%s"
        "(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;" % (
            temp0, "v%d" % (int(temp0[1:]) + 1), ext, hook),
        "    move-result-object %s" % temp0,
        "    move-object/from16 %s, %s" % (src_reg, temp0),
    ]


def _opcode(line):
    """Return an executable smali instruction, ignoring debug and labels."""
    text = line.strip()
    if not text or text.startswith(("#", ".", ":")):
        return None
    return text


def _writes_register(instruction, reg):
    """Conservative first-operand write check; unknown syntax fails closed."""
    if instruction is None:
        return False
    op = instruction.split(None, 1)[0]
    if op.startswith(("invoke-", "if-", "goto", "return", "throw", "monitor-", "aput", "iput", "sput", "filled-new-array")):
        return False
    # All relevant Dalvik writes have their destination first; an unknown
    # opcode is rejected rather than assumed to preserve the value.
    if not re.match(r"^(?:move|const|new-|iget|sget|aget|check-cast|instance-of|array-length|neg-|not-|int-|long-|float-|double-|add-|sub-|mul-|div-|rem-|and-|or-|xor-|shl-|shr-|ushr-|cmp)", op):
        raise PatchError("unknown instruction in stock register lifetime: %s" % instruction)
    rest = instruction[len(op):].strip()
    return bool(re.match(r"^" + re.escape(reg) + r"(?:\s*,|\s*$)", rest))


def verify_early_rule_site(lines, mstart, rule_idx, rule_reg, langs_reg,
                           replace_end, placeholder):
    """Accept the observed early-rule path only with a live joined language.

    Prove both arms assign the language register, join before the rule, and
    reject any subsequent write through the enabled-language substitution.
    """
    if langs_reg != "v8" or placeholder != "{ENABLED_LANGUAGES}":
        raise PatchError("unrecognized early-rule language register/site")
    joins = []
    for i in range(mstart, rule_idx):
        if re.fullmatch(r"\s*:goto_[0-9a-f]+\s*", lines[i]):
            joins.append(i)
    candidates = []
    for join in joins:
        label = lines[join].strip()
        defs = [i for i in range(mstart, join) if _opcode(lines[i]) and
                _writes_register(_opcode(lines[i]), langs_reg)]
        if len(defs) < 2 or not any(re.fullmatch(r"\s*goto\s+" + re.escape(label) + r"\s*", lines[k])
                                     for k in range(defs[-2] + 1, defs[-1])):
            continue
        if not re.fullmatch(r"move-object(?:/from16)?\s+" + langs_reg + r",\s*[vp]\d+", lines[defs[-2]].strip()):
            continue
        if not re.fullmatch(r"move-result-object\s+" + langs_reg, lines[defs[-1]].strip()):
            continue
        if any(_writes_register(_opcode(lines[k]), langs_reg) for k in range(join + 1, replace_end + 1)):
            continue
        candidates.append(join)
    if len(candidates) != 1:
        raise PatchError("early-rule enabled-language register lacks a verified two-arm join/lifetime")
    # Rule literal must be the replacement argument of the precise placeholder
    # substitution before either operand can be overwritten.
    placeholder_reg = None
    for i in range(rule_idx - 1, mstart - 1, -1):
        p = parse_const_string(lines[i])
        if p and p[1] == "{HINGLISH_OVERRIDE_RULE}":
            placeholder_reg = p[0]
            break
    if placeholder_reg is None:
        raise PatchError("early rule placeholder not found")
    for i in range(rule_idx + 1, replace_end + 1):
        instruction = _opcode(lines[i])
        if not instruction:
            continue
        invocation = parse_invoke(lines[i])
        if (invocation and invocation[1] == STRING_REPLACE and
                len(invocation[0]) == 3 and
                invocation[0][1:] == [placeholder_reg, rule_reg]):
            return
        if (_writes_register(instruction, rule_reg) or
                _writes_register(instruction, placeholder_reg)):
            break
    raise PatchError("early rule literal not consumed by expected String.replace")


def repair_stock_p0_window(lines, mstart, mend, saved_reg):
    """Repair only the five stock instructions whose p0 shifts past v15.

    The early-rule branch never reads saved_reg; it is a scratch register
    during the late stock instructions. Require exact original instructions
    and no other saved_reg use in the method before replacing anything.
    """
    if saved_reg != "v15":
        raise PatchError("unexpected stock scratch register")
    if any(re.search(r"\bv15\b", lines[i]) for i in range(mstart, mend + 1)):
        raise PatchError("stock scratch register is live")
    replacements = {
        'invoke-virtual {v2, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;':
            ['move-object/from16 v15, p0',
             'invoke-virtual {v2, v15}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;'],
        'invoke-virtual {p0, v0}, Lhpb;->b(Ljava/lang/Object;)Lauha;':
            ['move-object/from16 v15, p0',
             'invoke-virtual {v15, v0}, Lhpb;->b(Ljava/lang/Object;)Lauha;'],
        'move-object v4, p0': ['move-object/from16 v4, p0'],
        'iget-object p0, p0, Laazs;->c:Lauhe;':
            ['move-object/from16 v15, p0',
             'iget-object v15, v15, Laazs;->c:Lauhe;',
             'move-object/from16 p0, v15'],
        'invoke-static {v9, v0, p0}, Laugj;->t(Lauha;Laugd;Ljava/util/concurrent/Executor;)V':
            ['move-object/from16 v15, p0',
             'invoke-static {v9, v0, v15}, Laugj;->t(Lauha;Laugd;Ljava/util/concurrent/Executor;)V'],
    }
    seen = {k: 0 for k in replacements}
    for i in range(mstart, mend + 1):
        text = lines[i].strip()
        if text in seen:
            seen[text] += 1
    if any(count != 1 for count in seen.values()):
        raise PatchError("stock p0 window repair does not match five exact instructions")
    for i in range(mend, mstart - 1, -1):
        text = lines[i].strip()
        if text in replacements:
            indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
            lines[i:i+1] = [indent + op for op in replacements[text]]


def patch_method(lines, profile, fingerprints_ok):
    cls, name, proto = profile.method("cleanup_builder")
    is_static = " static " in (" " + lines[0])  # caller passes method lines only
    mstart, mend = method_bounds(lines, name, proto)
    header = lines[mstart]
    is_static = bool(re.search(r"\bstatic\b", header))
    body = lines[mstart:mend + 1]
    ext = profile.ext_class
    if any(ext in l for l in body):
        raise PatchError("method already references the extension runtime "
                         "(already patched?)")

    placeholder = profile.anchors["enabled_languages_placeholder"]
    langs_reg, result_reg, replace_end = find_enabled_languages_site(
        lines, mstart, mend, placeholder)

    rule_fp = profile.fingerprints["hinglish_override_rule"]["sha256"]
    rule_idx = None
    rule_reg = None
    for i in range(mstart, mend + 1):
        p = parse_const_string(lines[i])
        if p and sha256_text(p[1]) == rule_fp:
            rule_idx, rule_reg = i, p[0]
            break
    if rule_idx is None:
        raise PatchError("stock Hinglish override const-string not found in "
                         "kfd.d (fingerprint %s)" % rule_fp)
    early_rule = rule_idx < replace_end
    if early_rule:
        verify_early_rule_site(lines, mstart, rule_idx, rule_reg,
                               langs_reg, replace_end, placeholder)

    # Three temps: one dedicated save register for the enabled-languages
    # value (captured immediately after the String.replace so a later
    # const-string cannot clobber it), plus a contiguous invoke pair.
    base = bump_locals(lines, mstart, 3, proto, is_static)
    if base + 2 > 255:
        raise PatchError("method uses too many registers for 8-bit temps")
    saved_langs = "v%d" % base
    temp0 = "v%d" % (base + 1)

    if early_rule:
        # Growing the local window shifts p0 from v15 to v18. Only the five
        # verified narrow-form stock uses need a scratch/extended-form repair.
        # Do this before inserting hooks, which use the same otherwise-dead v15.
        repair_stock_p0_window(lines, mstart, mend, saved_langs)
        # Repair is downstream of both injection anchors; their indices hold.
        # Stock kfd.d has joined v8 before the rule; the rule is consumed
        # before the prompt reaches the enabled-language substitution.
        # Insert later Hook A first so the early rule index stays fixed.
        lines[replace_end + 1:replace_end + 1] = hook_snippet(
            temp0, result_reg, langs_reg, ext, PROMPT_HOOK)
        lines[rule_idx + 1:rule_idx + 1] = hook_snippet(
            temp0, rule_reg, langs_reg, ext, RULE_HOOK)
    else:
        # Later-rule fixture: save the languages register at Hook A, before
        # subsequent stock instructions can overwrite it at Hook B.
        lines[rule_idx + 1:rule_idx + 1] = hook_snippet(
            temp0, rule_reg, saved_langs, ext, RULE_HOOK)
        lines[replace_end + 1:replace_end + 1] = (
            ["    move-object/from16 %s, %s" % (saved_langs, langs_reg)]
            + hook_snippet(temp0, result_reg, langs_reg, ext, PROMPT_HOOK))
    return lines


def verify_prompt_owner(lines_by_class, profile):
    cls, name, proto = profile.method("prompt_owner")
    path_lines = lines_by_class.get(cls)
    if path_lines is None:
        raise PatchError("prompt owner class %s not found" % cls)
    mstart, mend = method_bounds(path_lines, name, proto)
    fp = profile.fingerprints["lite_cleanup_prompt"]["sha256"]
    for i in range(mstart, mend + 1):
        p = parse_const_string(path_lines[i])
        if p and sha256_text(p[1]) == fp:
            return True
    raise PatchError("Lite cleanup prompt fingerprint %s not found in %s->%s"
                     % (fp, cls, name))


def patch(apk, out_apk, profile, workdir, baksmali_jar, smali_jar,
          extension_dex=None):
    dexes = disassemble_all(apk, workdir, baksmali_jar)

    # 1. Fail-closed fingerprint sweep across the whole APK.
    hits = scan_fingerprints(dexes, profile.fingerprints)
    for key, fp in profile.fingerprints.items():
        if not hits[key]:
            raise PatchError("fingerprint %s (%s) not found anywhere in the "
                             "APK; refusing to patch an unrecognized build"
                             % (fp["sha256"], key))

    # 2. Locate the cleanup-builder method's dex.
    cls, name, proto = profile.method("cleanup_builder")
    target = None
    for dex_name, ddir in dexes:
        path = os.path.join(ddir, smali_class_path(cls))
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            try:
                method_bounds(lines, name, proto)
            except PatchError:
                continue
            target = (dex_name, ddir, path, lines)
            break
    if target is None:
        raise PatchError("cleanup builder %s->%s%s not found" % (cls, name, proto))

    dex_name, ddir, path, lines = target

    # 3. Verify the prompt-owner fingerprint before touching anything.
    pcls, pname, pproto = profile.method("prompt_owner")
    plines = None
    for dn2, dd2 in dexes:
        ppath = os.path.join(dd2, smali_class_path(pcls))
        if os.path.exists(ppath):
            with open(ppath, encoding="utf-8") as fh:
                cand = fh.read().splitlines()
            try:
                method_bounds(cand, pname, pproto)
                plines = cand
            except PatchError:
                continue
    verify_prompt_owner({pcls: plines} if plines else {}, profile)

    # 4. Rewrite the cleanup builder.
    new_lines = patch_method(lines, profile, hits)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(new_lines) + "\n")

    # 5. Reassemble only the touched dex.
    new_dex = os.path.join(workdir, "patched-" + dex_name)
    assembly_cmd = smali_prefix("smali", smali_jar) + ["a", ddir, "-o", new_dex]
    assembly = subprocess.run(assembly_cmd, capture_output=True, text=True)
    if (assembly.returncode != 0 or not os.path.isfile(new_dex) or
            os.path.getsize(new_dex) == 0):
        raise PatchError("smali failed or emitted no patched DEX "
                         "(exit %d):\n%s%s" % (
                             assembly.returncode, assembly.stdout,
                             assembly.stderr))

    # 6. Repack: copy every entry, swap the patched dex, append extension dex.
    with zipfile.ZipFile(apk) as zin, \
            zipfile.ZipFile(out_apk, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == dex_name:
                with open(new_dex, "rb") as fh:
                    zout.writestr(item.filename, fh.read())
            else:
                zout.writestr(item, zin.read(item.filename))
        if extension_dex:
            existing = [d for d, _ in dexes]
            nxt = "classes%d.dex" % (len(existing) + 1)
            with open(extension_dex, "rb") as fh:
                zout.writestr(nxt, fh.read())
    return {"patched_dex": dex_name, "out": out_apk,
            "extension_dex": extension_dex}


# ----------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["analyze", "patch"])
    ap.add_argument("--apk", required=True)
    ap.add_argument("--out")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--workdir", default="/tmp/dex-patch-work")
    ap.add_argument("--baksmali-jar", default=os.environ.get(
        "BAKSMALI_JAR", "tools/baksmali-2.5.2.jar"))
    ap.add_argument("--smali-jar", default=os.environ.get(
        "SMALI_JAR", "tools/smali-2.5.2.jar"))
    ap.add_argument("--extension-dex")
    args = ap.parse_args(argv)

    profile = Profile(args.profile)
    if os.path.isdir(args.workdir):
        shutil.rmtree(args.workdir)
    os.makedirs(args.workdir)

    try:
        if args.command == "analyze":
            report = analyze(args.apk, profile, args.workdir,
                             args.baksmali_jar)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0
        if not args.out:
            ap.error("patch requires --out")
        result = patch(args.apk, args.out, profile, args.workdir,
                       args.baksmali_jar, args.smali_jar,
                       args.extension_dex)
        print(json.dumps(result, indent=2))
        return 0
    except PatchError as exc:
        print("FAIL-CLOSED ABORT: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
