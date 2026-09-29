#!/usr/bin/env python3
"""Pinned v32 drag/order dependency guard; no Android behavior verdict."""
import hashlib
import unittest
from pathlib import Path
from zipfile import ZipFile

STOCK=Path('/tmp/rambler-bases/gboard-beta-arm64.apk')
V32=Path('/downloads/rambler-bangla-v32.apk')
SHAS={'stock':'2672a08a0292a307b9f62cd0fa6f48f3bc2334a2f2d9daff7db9d54fc4a2a7e3',
      'v32':'ce0d7e6710711f972e24ece2e838a3f51aff5184aeaeb78590dc1b14f182bd64'}
EXT='Lcom/akshaykadam/pixelboard/extension/rambler/'


def method(dex,cls,name,descriptor):
    obj=dex.get_class(cls)
    assert obj is not None, cls
    found=[m for m in obj.get_methods() if m.get_name()==name and m.get_descriptor().replace(' ','')==descriptor]
    assert len(found)==1,(cls,name,descriptor,len(found))
    return [(i.get_name(),i.get_output()) for i in found[0].get_instructions()]


def refs(instructions,substring):
    return [i for i,(op,arg) in enumerate(instructions) if substring in arg and op.startswith('invoke-')]

class PinnedDragMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not STOCK.is_file() or not V32.is_file():raise unittest.SkipTest('pinned APK absent')
        try:
            from androguard.core.dex import DEX
            from loguru import logger
            logger.remove()
        except ImportError as exc:
            raise unittest.SkipTest('Androguard missing '+str(exc))
        for key,path in [('stock',STOCK),('v32',V32)]:
            sha=hashlib.sha256()
            with path.open('rb') as f:
                for chunk in iter(lambda:f.read(1048576),b''):sha.update(chunk)
            assert sha.hexdigest()==SHAS[key], 'pinned SHA drift'
        with ZipFile(STOCK) as a,ZipFile(V32) as b:
            cls.stock2=DEX(a.read('classes2.dex'))
            cls.v322=DEX(b.read('classes2.dex'))
            cls.v323=DEX(b.read('classes3.dex'))
            cls.extension=DEX(b.read('classes.dex'))

    def test_drag_attach_is_pinned_only_and_adapter_bound(self):
        v=method(self.v323,'Lkut;','p','(Lra;I)V')
        a=method(self.extension,EXT+'GboardRamblerClipDrag;','attach','(Lkut;Lra;Ljava/lang/Object;)V')
        self.assertEqual(len(refs(v,'GboardRamblerClipDrag;->attach')),1)
        self.assertEqual(len(refs(a,'GboardRamblerClipOrder;->init')),1)
        self.assertEqual(len(refs(a,'ClipAccess;->isPinned')),1)
        self.assertEqual(len(refs(a,'View;->setOnTouchListener')),2)
        self.assertFalse(refs(method(self.stock2,'Lkut;','p','(Lra;I)V'),'GboardRamblerClipDrag;->attach'))

    def test_hold_then_move_and_persistence_dependencies(self):
        e=self.extension
        drag=EXT+'GboardRamblerClipDrag;'
        handle=method(e,drag,'handle','(Landroid/view/View;Landroid/view/MotionEvent;)Z')
        follow=method(e,drag,'follow','(Landroid/view/View;Landroid/view/MotionEvent;)V')
        finish=method(e,drag,'finishDrag','(Landroid/view/View;)V')
        order=EXT+'GboardRamblerClipOrder;'
        save=method(e,order,'save','(Ljava/util/List;)V')
        self.assertEqual(len(refs(handle,'ViewConfiguration;->getLongPressTimeout')),1)
        self.assertEqual(len(refs(handle,'View;->postDelayed')),1)
        self.assertEqual(len(refs(handle,'ViewConfiguration;->getScaledTouchSlop')),1)
        self.assertEqual(len(refs(follow,'ClipAccess;->isPinned')),1)
        self.assertEqual(len(refs(follow,'Lkut;->eH')),1)
        self.assertEqual(len(refs(follow,'GboardRamblerClipOrder;->save')),1)
        self.assertEqual(len(refs(finish,'GboardRamblerClipOrder;->save')),1)
        self.assertEqual(len(refs(save,'ClipAccess;->isPinned')),1)
        self.assertEqual(len(refs(save,'ClipAccess;->id')),1)
        self.assertIn(('const-string','v0, "pinned_ids"'),save)
        self.assertIn(('const-string','v0, "rambler_clip_order"'),save)
        for cls,name,sig in [('Lkta;','b','(Ljava/lang/Object;)V'),('Lkut;','E','(Landroid/util/SparseArray;Ljava/util/List;I)V')]:
            self.assertEqual(len(refs(method(self.v323,cls,name,sig),'GboardRamblerClipOrder;->apply')),1)
            self.assertFalse(refs(method(self.stock2,cls,name,sig),'GboardRamblerClipOrder;->apply'))

if __name__=='__main__':unittest.main()
