#!/usr/bin/env python3
"""Read-only pinned dependency closure for v32's clip drag; not a port."""
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile

V32=Path('/downloads/rambler-bangla-v32.apk')
EXPECTED='ce0d7e6710711f972e24ece2e838a3f51aff5184aeaeb78590dc1b14f182bd64'
PREFIX='Lcom/akshaykadam/pixelboard/extension/rambler/'
ROOTS=('ClipAccess','GboardRamblerClipOrder','GboardRamblerClipDrag','GboardRamblerClipSmooth')
EXPECTED_CLOSURE=set(ROOTS)|{'GboardRamblerClipOrder$$ExternalSyntheticLambda0','GboardRamblerClipDrag$1'}


def inventory(apk=V32):
    h=hashlib.sha256()
    with Path(apk).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    if h.hexdigest()!=EXPECTED:raise ValueError('v32 APK drift')
    from androguard.core.dex import DEX
    from loguru import logger
    logger.remove()
    with ZipFile(apk) as z:
        raw=z.read('classes.dex')
    dex=DEX(raw)
    queue=list(ROOTS);seen=set();links={}
    while queue:
        name=queue.pop(0)
        if name in seen:continue
        seen.add(name)
        cls=dex.get_class(PREFIX+name+';')
        if cls is None:raise ValueError('missing extension dependency '+name)
        code='\n'.join(i.get_output() for m in cls.get_methods() for i in m.get_instructions())
        refs=sorted(set(re.findall(r'Lcom/akshaykadam/pixelboard/extension/[^;]+;',code)))
        outsiders=[ref for ref in refs if not ref.startswith(PREFIX)]
        if outsiders:raise ValueError('unscoped extension reference '+repr(outsiders))
        links[name]=sorted(ref[len(PREFIX):-1] for ref in refs if ref!=PREFIX+name+';')
        queue.extend(links[name])
    if seen!=EXPECTED_CLOSURE:raise ValueError('drag closure changed: '+repr(sorted(seen)))
    return {'apk_sha256':EXPECTED, 'extension_dex_sha256':hashlib.sha256(raw).hexdigest(),
            'class_count':len(seen),'classes':sorted(seen),'references':links,
            'status':'DEPENDENCY_MAP_ONLY_NO_BUILD'}


if __name__=='__main__':
    from loguru import logger
    logger.remove()
    print(json.dumps(inventory(),sort_keys=True,indent=2))
