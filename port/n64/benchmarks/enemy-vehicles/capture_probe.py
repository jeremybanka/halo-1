"""Fail-fast Battle Creek allocation/render check; not a performance benchmark."""
import subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'build/pve-vehicles'
rom=next((OUT/'map-probe').glob('*.z64'));path=OUT/'map-probe-native.log';complete=False
with path.open('w') as log:
    proc=subprocess.Popen(['/Applications/ares.app/Contents/MacOS/ares','--settings-file',str(OUT/'ares.bml'),'--no-file-prompt',str(rom)],stdout=log,stderr=subprocess.STDOUT)
    start=time.monotonic()
    try:
        while proc.poll() is None and time.monotonic()-start<60:
            time.sleep(.5);text=path.read_text(errors='replace')
            if any(x in text.lower() for x in ('assertion failed','assertf','rdpq error')):break
            if 'CENSUS tick=0 camera=3 ' in text:complete=True;break
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
assert complete,'Battle Creek native allocation/render probe failed'
print('PASS Battle Creek loaded and rendered all four cameras')
