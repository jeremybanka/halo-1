import subprocess,time,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'build/scope-fix';case=sys.argv[1];PHOTO=OUT/case;logpath=OUT/(case+'-native.log')
m=json.loads(next(PHOTO.glob('*.build.json')).read_text())
with logpath.open('w') as log:
 p=subprocess.Popen(['/Applications/ares.app/Contents/MacOS/ares','--settings-file',str(ROOT/'build/pve-vehicles/ares.bml'),'--no-file-prompt',m['rom']['path']],stdout=log,stderr=subprocess.STDOUT)
 start=time.monotonic()
 try:
  while p.poll() is None and time.monotonic()-start<240:
   time.sleep(.5);s=logpath.read_text(errors='replace')
   if 'M64_POLISH_QA PASS' in s or 'assertion failed' in s.lower():break
 finally:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
s=logpath.read_text(errors='replace');assert 'M64_POLISH_QA PASS' in s,s[-2000:]
sys.path.insert(0,str(ROOT/'port/n64/benchmarks/firefight-limited'));from decode_photo import decode
for page in re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END',s,re.S):
 n=int(re.search(r'tick=(\d+)',page).group(1));raw=PHOTO/f'photo-{n}.log';raw.write_text(page);decode(raw,PHOTO/f'photo-{n}.png');raw.unlink()
print('PASS 10 scope photos')
