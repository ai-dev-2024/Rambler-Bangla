#!/usr/bin/env python3
"""Read-only descriptor/dependency inventory for pinned stock and v32 APKs.

Requires androguard. No APK mutation. Emits a JSON report only.
"""
import argparse
from collections import Counter
import hashlib
import json
import re
import zipfile
from loguru import logger
logger.remove()
from androguard.core.dex import DEX

STOCK_SHA = '2672a08a0292a307b9f62cd0fa6f48f3bc2334a2f2d9daff7db9d54fc4a2a7e3'
V32_SHA = 'ce0d7e6710711f972e24ece2e838a3f51aff5184aeaeb78590dc1b14f182bd64'
PREFIX = 'Lcom/akshaykadam/pixelboard/extension/'


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def inventory(path):
    dex_classes = {}
    with zipfile.ZipFile(path) as z:
        for name in sorted(n for n in z.namelist() if re.fullmatch(r'classes(?:\d+)?\.dex', n)):
            dex_classes[name] = DEX(z.read(name))
    by_descriptor = {}
    for dex_name, dex in dex_classes.items():
        for cls in dex.get_classes():
            descriptor = cls.get_name()
            if descriptor in by_descriptor:
                raise ValueError('duplicate class descriptor: ' + descriptor)
            by_descriptor[descriptor] = dex_name
    return dex_classes, by_descriptor


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stock', required=True)
    p.add_argument('--v32', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    if sha(a.stock) != STOCK_SHA or sha(a.v32) != V32_SHA:
        raise ValueError('pinned APK hash mismatch')
    _, stock = inventory(a.stock)
    _, v32 = inventory(a.v32)
    if not set(stock).issubset(v32):
        raise ValueError('v32 is missing stock descriptors')
    new = set(v32) - set(stock)
    extensions = {n for n in new if n.startswith(PREFIX)}
    if len(extensions) != 270 or len(new) != 1356:
        raise ValueError('unexpected extension/support class inventory')
    if any(v32[n] != 'classes.dex' for n in new):
        raise ValueError('unexpected v32-only class dex position')
    report = {
        'stock_sha256': STOCK_SHA, 'v32_sha256': V32_SHA,
        'stock_class_count': len(stock), 'v32_class_count': len(v32),
        'v32_new_class_count': len(new),
        'v32_new_extension_count': len(extensions),
        'v32_new_support_count': len(new - extensions),
        'v32_new_by_dex': dict(Counter(v32[n] for n in new)),
        'extension_by_namespace': dict(Counter(n.split('/')[4] for n in extensions)),
        'moved_stock_by_dex_pair': {' -> '.join(pair): count for pair, count in
            Counter((stock[n], v32[n]) for n in stock if stock[n] != v32[n]).items()},
        'host_components': [
            'Lcom/akshaykadam/pixelboard/extension/settings/GboardPatchesSettingsActivity;',
            'Lcom/akshaykadam/pixelboard/extension/settings/GboardPatchesSettingsProvider;'],
        'v32_new_descriptors': sorted(new),
    }
    for component in report['host_components']:
        if component not in extensions:
            raise ValueError('host component not in new extension classes: ' + component)
    with open(a.out, 'w') as fh:
        json.dump(report, fh, indent=2)
    print('stock=%d v32=%d new=%d extensions=%d support=%d' %
          (len(stock), len(v32), len(new), len(extensions), len(new-extensions)))


if __name__ == '__main__':
    main()
