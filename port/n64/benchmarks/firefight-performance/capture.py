#!/usr/bin/env python3
"""Bounded Ares capture. Terminates only its own emulator subprocess."""
import argparse,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('rom',type=Path);p.add_argument('settings',type=Path);p.add_argument('log',type=Path);p.add_argument('--observations',type=int,default=75);a=p.parse_args()
with a.log.open('w') as log:
    proc=subprocess.Popen(['/Applications/ares.app/Contents/MacOS/ares','--settings-file',str(a.settings.resolve()),'--no-file-prompt',str(a.rom.resolve())],stdout=log,stderr=subprocess.STDOUT)
    print('Started owned Ares PID',proc.pid,flush=True);start=time.monotonic();complete=False
    try:
        while proc.poll() is None and time.monotonic()-start<240:
            time.sleep(.5);text=a.log.read_text(errors='replace')
            if text.count('PERF views=')>=a.observations:complete=True;break
            if 'assertion failed' in text.lower() or 'assertf' in text.lower():break
    finally:
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
    print('Complete:',complete,'observations:',a.log.read_text(errors='replace').count('PERF views='),flush=True)
    if not complete:raise SystemExit(1)
