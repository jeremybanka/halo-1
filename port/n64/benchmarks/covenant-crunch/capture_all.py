"""One owned emulator at a time: matched live performance, then frozen checks."""
import argparse,subprocess,sys,shutil,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--settings',type=Path,required=True);a=p.parse_args();out=a.capture.resolve();settings=out/'checks-ares.bml';shutil.copyfile(a.settings,settings)
def run(cmd):subprocess.run([sys.executable,*map(str,cmd)],cwd=ROOT,check=True)
for root,extra in [('perf',['--kinds','perf','--players','4']),('perf',['--kinds','perf','--players','1','2','3']),('perf',['--kinds','opening']),('gpu',['--gpu','--kinds','perf','--players','4'])]:
 run([HERE/'run_matrix.py','capture','--output',out/root,'--model-bank',out/'bank','--settings',settings,'--resume',*extra])
for name in ('crowded-1','crowded-60','crowded-180','delivery-300','timing'):
 for version in ('baseline','candidate'):
  case=version+'-'+name;rom=next((out/'checks'/case).glob('*.z64'));log=out/'checks'/(case+'-native.log')
  print('CHECK',case,flush=True)
  run([HERE.parent/'firefight-drawing/capture.py',rom,settings,log])
print('FRONTEND',flush=True);rom=next((out/'frontend-4').glob('*.z64'));log=out/'frontend-4-native.log'
with log.open('w') as f:
 proc=subprocess.Popen(['/Applications/ares.app/Contents/MacOS/ares','--settings-file',str(settings),'--no-file-prompt',str(rom)],stdout=f,stderr=subprocess.STDOUT)
 begin=time.monotonic();complete=False
 try:
  while proc.poll() is None and time.monotonic()-begin<240:
   time.sleep(.5);text=log.read_text(errors='replace')
   if any(x in text.lower() for x in ('assertion failed','assertf','rdpq error','rdpq warning')):break
   if 'FIREFIGHT_QA PASS players=4' in text:complete=True;break
 finally:
  proc.terminate()
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
 assert complete,'Frontend lifecycle did not complete'
print('ALL CAPTURES COMPLETE',flush=True)
