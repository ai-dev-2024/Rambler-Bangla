#!/usr/bin/env python3
"""Emulator-only smoke for clipboard app-marked preview policy; no claim of user trace reproduction."""
import json, os, re, subprocess, sys, time, xml.etree.ElementTree as ET
OUT=os.environ.get('PROBE_OUT','clipmask-artifacts')
PKG='com.aidev2024.ramblerbangla'
FIX='test.clip.fixture'
UNMARKED='ordinary.probe@example.test'
MARKED='marked.probe@example.test'
os.makedirs(OUT,exist_ok=True)
results={}
def adb(*args,check=False):
 p=subprocess.run(['adb',*args],capture_output=True,text=True,timeout=75)
 if check and p.returncode: raise RuntimeError(f'adb {args[0]} failed: {p.stderr[-300:]}')
 return p.stdout
def snap(label):
 xml=''
 for flag in ('--windows',None):
  adb('shell','rm','-f','/sdcard/clipmask.xml')
  adb('shell','uiautomator','dump',*([flag] if flag else []),'/sdcard/clipmask.xml')
  xml=adb('exec-out','cat','/sdcard/clipmask.xml')
  if '<hierarchy' in xml: break
 open(f'{OUT}/{label}.xml','w').write(xml)
 with open(f'{OUT}/{label}.png','wb') as f:
  subprocess.run(['adb','exec-out','screencap','-p'],stdout=f,check=True,timeout=75)
 nodes=[]
 if '<hierarchy' not in xml: return nodes
 root=ET.fromstring(xml[xml.index('<'):])
 for x in root.iter('node'):
  b=list(map(int,re.findall(r'\d+',x.get('bounds',''))))
  if len(b)==4:
   nodes.append(dict(text=x.get('text',''),desc=x.get('content-desc',''),pkg=x.get('package',''),cls=x.get('class',''),xy=((b[0]+b[2])//2,(b[1]+b[3])//2)))
 return nodes
def find(nodes,pat,pkg=None):
 r=re.compile(pat,re.I)
 return next((n for n in nodes if (not pkg or n['pkg']==pkg) and (r.search(n['text']) or r.search(n['desc']))),None)
def tap(n):
 adb('shell','input','tap',*[str(i) for i in n['xy']],check=True);time.sleep(1.5)
def ime_nodes(label): return [n for n in snap(label) if n['pkg']==PKG]
def field():
 ns=snap('fixture')
 n=find(ns,'Tap here for keyboard clipboard',FIX)
 if not n: raise RuntimeError('fixture text field absent')
 tap(n);return n
def clipboard(label):
 ns=ime_nodes(label+'-ime')
 if not ns: raise RuntimeError('keyboard invisible')
 if find(ns,r'^hide clipboard$',PKG):return ns
 n=find(ns,r'^clipboard$',PKG)
 if not n:
  more=find(ns,'open features menu',PKG)
  if more:tap(more);ns=ime_nodes(label+'-menu');n=find(ns,r'^clipboard$',PKG)
 if not n:raise RuntimeError('clipboard button absent')
 tap(n);return ime_nodes(label+'-board')
def copy_case(label,button):
 adb('shell','am','start','-n',FIX+'/.MainActivity',check=True);time.sleep(2)
 ns=snap(label+'-fixture')
 n=find(ns,'^'+button+'$',FIX)
 if not n:raise RuntimeError('copy button absent: '+button)
 tap(n);field();return clipboard(label)
def evaluate(nodes,case,expected):
 values=[n['text'] for n in nodes if n['pkg']==PKG]+[n['desc'] for n in nodes if n['pkg']==PKG]
 strings='\n'.join(values)
 token=MARKED if case.startswith('marked') else UNMARKED
 bullets=[x for x in values if len(x)==len(token) and set(x.strip())=={'•'}]
 outcome={'raw_visible':token in strings,'expected_raw_visible':expected,'bullet_candidates':bullets[:3], 'board_node_count':len(nodes)}
 results[case]=outcome
 if outcome['raw_visible']!=expected:raise AssertionError(f'{case}: raw visibility mismatch: {outcome}')
 if not expected and len(bullets)!=1:raise AssertionError(f'{case}: expected one exact-length masked tile for the latest marked item; got {bullets}')
def main():
 ime=''
 for i in range(20):
  ime=next((x.strip() for x in adb('shell','ime','list','-a','-s').splitlines() if x.strip().startswith(PKG+'/')),'')
  if ime:break
  time.sleep(3)
 if not ime:raise RuntimeError('Rambler IME not registered')
 adb('shell','ime','enable',ime,check=True);adb('shell','ime','set',ime,check=True)
 adb('shell','am','start','-n',FIX+'/.MainActivity',check=True);time.sleep(2)
 field();ns=clipboard('init')
 on=find(ns,'turn on clipboard',PKG)
 if on:tap(on);ns=ime_nodes('enabled')
 hide=find(ns,'^hide clipboard$',PKG)
 if hide:tap(hide)
 evaluate(copy_case('unmarked','Copy unmarked email'),'unmarked',True)
 evaluate(copy_case('marked','Copy app-marked email'),'marked',False)
 # The fresh emulator has no clipboard history before these controlled two writes.
 # Check the one exact-length masked tile, then go through the app's real settings UI.
 adb('shell','am','start','-n',PKG+'/com.google.android.apps.inputmethod.latin.preference.SettingsActivity',check=True);time.sleep(2)
 ns=snap('settings-main')
 n=find(ns,r'^Advanced settings$',PKG)
 for i in range(4):
  if n:break
  adb('shell','input','swipe','540','1900','540','650','400',check=True);time.sleep(0.7)
  ns=snap(f'settings-main-scroll-{i+1}')
  n=find(ns,r'^Advanced settings$',PKG)
 if not n:raise RuntimeError('Advanced settings entry not found after scrolling')
 tap(n);ns=snap('settings-advanced')
 n=find(ns,r'^App-marked sensitive text$',PKG)
 for i in range(8):
  if n:break
  adb('shell','input','swipe','540','1900','540','650','400',check=True);time.sleep(0.7)
  ns=snap(f'settings-advanced-scroll-{i+1}')
  n=find(ns,r'^App-marked sensitive text$',PKG)
 if not n:raise RuntimeError('App-marked sensitive text entry not found under Advanced after scrolling')
 snap('settings-toggle-before')
 n=find(ns,r'^App-marked sensitive text$',PKG)
 if not n:raise RuntimeError('App-marked sensitive text toggle not found')
 # A switch may be a sibling with checked state: retain full XML to audit before/after.
 tap(n);snap('settings-toggled-off')
 ns=copy_case('marked-off','Copy app-marked email')
 evaluate(ns,'marked-off',True)
 adb('shell','am','start','-n',PKG+'/com.google.android.apps.inputmethod.latin.preference.SettingsActivity',check=True);time.sleep(2)
 ns=snap('settings-main-again'); n=find(ns,r'^Advanced settings$',PKG)
 for i in range(4):
  if n:break
  adb('shell','input','swipe','540','1900','540','650','400',check=True);time.sleep(0.7)
  ns=snap(f'settings-main-again-scroll-{i+1}');n=find(ns,r'^Advanced settings$',PKG)
 if not n:raise RuntimeError('Advanced settings entry absent during re-enable')
 tap(n);ns=snap('settings-advanced-again');n=find(ns,r'^App-marked sensitive text$',PKG)
 for i in range(8):
  if n:break
  adb('shell','input','swipe','540','1900','540','650','400',check=True);time.sleep(0.7)
  ns=snap(f'settings-advanced-again-scroll-{i+1}');n=find(ns,r'^App-marked sensitive text$',PKG)
 if not n:raise RuntimeError('mask toggle absent during re-enable')
 tap(n);snap('settings-reenabled')
 ns=copy_case('marked-reenabled','Copy app-marked email');evaluate(ns,'marked-reenabled',False)
 print('Default ON, UI-toggled OFF and re-enabled ON checked on Android emulator.')
if __name__=='__main__':
 code=0
 try:main();results['status']='PASS_ON_AND_OFF'
 except Exception as e:results['status']='FAIL_OR_UNTESTED';results['error']=repr(e);code=1
 results['logcat_fatal']=bool(re.search(r'FATAL EXCEPTION[^\n]*\n[^\n]*Process: '+re.escape(PKG),adb('logcat','-d','-v','threadtime')))
 if results['logcat_fatal']:code=1
 open(f'{OUT}/results.json','w').write(json.dumps(results,indent=2))
 print(json.dumps(results,indent=2));sys.exit(code)
