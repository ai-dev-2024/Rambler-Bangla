#!/usr/bin/env python3
import subprocess,time,xml.etree.ElementTree as E,re,os,json
O='clipmask-artifacts';P='com.aidev2024.ramblerbangla';os.makedirs(O,exist_ok=True)
def a(*x):
 r=subprocess.run(['adb',*x],capture_output=True,text=True,timeout=90);return r.stdout+'\n'+r.stderr
try:
 ime=next(x for x in a('shell','ime','list','-a','-s').splitlines() if x.startswith(P+'/'))
 a('shell','ime','enable',ime);a('shell','ime','set',ime)
 a('shell','am','start','-n',P+'/com.google.android.apps.inputmethod.latin.preference.SettingsActivity');time.sleep(3)
 for stage,pat in [('main','Advanced settings'),('advanced','App-marked sensitive text')]:
  for j in range(8):
   a('shell','uiautomator','dump','/sdcard/view.xml');z=a('exec-out','cat','/sdcard/view.xml');open(f'{O}/{stage}-{j}.xml','w').write(z)
   if '<hierarchy' not in z:time.sleep(2);continue
   m=next((n for n in E.fromstring(z[z.index('<'):]).iter('node') if n.get('text')==pat),None)
   if m:break
   a('shell','input','swipe','540','1900','540','650','400')
  if not m:raise Exception('missing '+pat)
  b=list(map(int,re.findall(r'\d+',m.get('bounds'))));x=(b[0]+b[2])//2;y=(b[1]+b[3])//2
  if stage=='main':a('shell','input','tap',str(x),str(y));time.sleep(2)
  else:
   for k,(xx,yy) in enumerate([(x,y),(x+300,y)]):
    a('logcat','-c');a('shell','input','tap',str(xx),str(yy));time.sleep(1)
    open(f'{O}/tap-{k}.log','w').write(a('logcat','-d','-v','threadtime'))
    a('shell','uiautomator','dump','/sdcard/after.xml');open(f'{O}/tap-{k}.xml','w').write(a('exec-out','cat','/sdcard/after.xml'))
 print('captured')
except Exception as e:
 open(f'{O}/error.txt','w').write(repr(e));raise
