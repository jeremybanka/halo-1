#!/usr/bin/env python3
"""Capture the 51-frame native motion fixture, terminating only the owned Ares."""
import argparse,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('rom',type=Path);p.add_argument('settings',type=Path);p.add_argument('log',type=Path);a=p.parse_args()
with a.log.open('w') as log:
 proc=subprocess.Popen(['/Applications/ares.app/Contents/MacOS/ares','--settings-file',str(a.settings.resolve()),'--no-file-prompt',str(a.rom.resolve())],stdout=log,stderr=subprocess.STDOUT)
 start=time.monotonic();complete=False
 try:
  while proc.poll() is None and time.monotonic()-start<240:
   time.sleep(.5);text=a.log.read_text(errors='replace')
   if text.count('FF_PHOTO_END')==51:complete=True;break
   if 'assertion failed' in text.lower() or 'assertf' in text.lower():break
 finally:
  proc.terminate()
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
 print(a.log,'complete',complete,'frames',a.log.read_text(errors='replace').count('FF_PHOTO_END'))
 if not complete:raise SystemExit(1)
