#!/usr/bin/env python3
"""Fail-closed staging-only Lkut.F recents adapter hook, unsigned output only."""
import argparse
import hashlib
import re
import subprocess
from pathlib import Path
from zipfile import ZipFile

EXPECTED_APK_SHA = '8911ca4dc4a718812fe1d6782b735bbffa08357dae1345cb65ff9e2381fcd695'
EXPECTED_DEX_SHA = 'c338d6f8d3b08a98b2365f10747e7e75785a199ce0c8e2e7905b6a025046d2f9'
METHOD = re.compile(r'(?ms)^\.method public final F\(\)V\n.*?^\.end method$')
ANCHOR = re.compile(r'(?m)^(\s*)const/4 v4, 0x5\s*$')
HOOK = ('iget-object v4, p0, Lkut;->e:Landroid/content/Context;\n'
        'invoke-static {v4}, Lcom/akshaykadam/pixelboard/extension/rambler/'
        'GboardRamblerClipRecents;->read(Landroid/content/Context;)I\n'
        'move-result v4')


def patch(text):
    matches = list(METHOD.finditer(text))
    if len(matches) != 1:
        raise ValueError('Lkut.F method count drift')
    method = matches[0].group()
    if '.registers 6' not in method or 'GboardRamblerClipRecents;' in method:
        raise ValueError('Lkut.F register count or existing hook drift')
    hits = list(ANCHOR.finditer(method))
    if len(hits) != 1:
        raise ValueError('Lkut.F literal anchor count drift')
    if not all(x in method for x in ('iget-object v2, p0, Lkut;->o:Ljava/util/List;',
                                     'invoke-interface {v2, v1}, Ljava/util/List;->remove(I)Ljava/lang/Object;',
                                     'invoke-virtual {p0, v1}, Lpt;->n(I)V')):
        raise ValueError('Lkut.F adapter ownership drift')
    margin = hits[0].group(1)
    amended = ANCHOR.sub(margin + HOOK.replace('\n', '\n' + margin), method, count=1)
    return text[:matches[0].start()] + amended + text[matches[0].end():]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--in-apk', required=True)
    p.add_argument('--out-apk', required=True)
    p.add_argument('--work', required=True)
    a = p.parse_args()
    if Path(a.out_apk).exists():
        raise ValueError('refusing to overwrite an existing output')
    if hashlib.sha256(Path(a.in_apk).read_bytes()).hexdigest() != EXPECTED_APK_SHA:
        raise ValueError('staging input APK SHA drift')
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    with ZipFile(a.in_apk) as z:
        dex = z.read('classes2.dex')
        if hashlib.sha256(dex).hexdigest() != EXPECTED_DEX_SHA:
            raise ValueError('staging classes2.dex SHA drift')
        if 'classes6.dex' not in z.namelist():
            raise ValueError('staging shell classes6.dex missing')
    from androguard.core.dex import DEX
    from loguru import logger
    logger.remove()
    with ZipFile(a.in_apk) as zipped:
        ext = DEX(zipped.read('classes6.dex'))
    if not ext.get_class('Lcom/akshaykadam/pixelboard/extension/rambler/GboardRamblerClipRecents;'):
        raise ValueError('staging recents class missing')
    inp = work / 'classes2.dex'
    inp.write_bytes(dex)
    root = Path(__file__).resolve().parents[1]
    cp = ':'.join(str(root / 'tools' / n) for n in (root / 'tools/smali.cp').read_text().strip().split(':'))
    dis = work / 'dis'
    subprocess.run(['java', '-cp', cp, 'org.jf.baksmali.Main', 'd', str(inp), '-o', str(dis)], check=True)
    smali = dis / 'kut.smali'
    smali.write_text(patch(smali.read_text()))
    target = work / 'classes2-patched.dex'
    subprocess.run(['java', '-cp', cp, 'org.jf.smali.Main', 'a', str(dis), '-o', str(target)], check=True)
    from androguard.core.dex import DEX
    parsed = DEX(target.read_bytes())
    cls = parsed.get_class('Lkut;')
    f = [m for m in cls.get_methods() if m.get_name() == 'F' and m.get_descriptor() == '()V']
    if len(f) != 1 or sum('GboardRamblerClipRecents;->read' in i.get_output()
                          for i in f[0].get_instructions()) != 1:
        raise ValueError('assembled recents hook missing/duplicated')
    with ZipFile(a.in_apk) as before, ZipFile(a.out_apk, 'w') as after:
        for item in before.infolist():
            after.writestr(item, target.read_bytes() if item.filename == 'classes2.dex'
                           else before.read(item.filename))
    with ZipFile(a.in_apk) as before, ZipFile(a.out_apk) as after:
        if after.testzip() is not None or set(before.namelist()) != set(after.namelist()):
            raise ValueError('output ZIP integrity or entries drift')
        changed = [n for n in before.namelist() if before.read(n) != after.read(n)]
        if changed != ['classes2.dex']:
            raise ValueError('output ZIP changed unexpected entries: ' + repr(changed))
    print('unsigned-only', 'dex_before=' + EXPECTED_DEX_SHA,
          'dex_after=' + hashlib.sha256(target.read_bytes()).hexdigest(),
          'apk_sha=' + hashlib.sha256(Path(a.out_apk).read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
