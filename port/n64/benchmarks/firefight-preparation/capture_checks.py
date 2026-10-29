#!/usr/bin/env python3
"""Serialize native photo, graphics and frontend checks; own every emulator PID."""
import argparse,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
def main():
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--settings',type=Path,required=True);p.add_argument('--model-bank',type=Path,required=True);p.add_argument('--wait-matrix-log',type=Path);a=p.parse_args();out=a.capture.resolve()
    if a.wait_matrix_log:
        begin=time.monotonic()
        while True:
            text=a.wait_matrix_log.read_text()
            if text.count('Complete: True observations:')==16:break
            if 'Traceback' in text or time.monotonic()-begin>3600:raise RuntimeError('Matrix did not finish; no additional emulator launched')
            time.sleep(1)
    settings=out/'checks-ares.bml';shutil.copyfile(a.settings,settings)
    for version in ('before','after'):
        print('PHOTO',version,flush=True);rom=next((out/('photo-'+version)).glob('*.z64'))
        subprocess.run([sys.executable,str(ROOT/'port/n64/benchmarks/covenant-models/capture.py'),str(rom),str(settings),str(out/('photo-'+version+'-native.log'))],check=True)
    print('GRAPHICS',flush=True)
    subprocess.run([sys.executable,str(Path(__file__).with_name('run_matrix.py')),'capture','--output',str(out/'gpu'),'--model-bank',str(a.model_bank),'--settings',str(settings),'--gpu','--kinds','perf','--players','4'],check=True)
    print('FRONTEND',flush=True);rom=next((out/'frontend-4').glob('*.z64'));path=out/'frontend-4-native.log'
    with path.open('w') as log:
        proc=subprocess.Popen(['/Applications/ares.app/Contents/MacOS/ares','--settings-file',str(settings),'--no-file-prompt',str(rom)],stdout=log,stderr=subprocess.STDOUT)
        begin=time.monotonic();complete=False
        try:
            while proc.poll() is None and time.monotonic()-begin<240:
                time.sleep(.5);text=path.read_text(errors='replace')
                if 'FIREFIGHT_QA PASS players=4' in text:complete=True;break
                if any(x in text.lower() for x in ('assertion failed','assertf','rdpq error','rdpq warning')):break
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        assert complete,'Frontend did not complete'
    print('PASS native photos, graphics and four-player frontend lifecycle',flush=True)
if __name__=='__main__':main()
