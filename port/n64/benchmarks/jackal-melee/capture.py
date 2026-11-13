"""Capture the owned native melee fixture; invoke through workspace.py run."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'))
from build import parse_args

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--settings',type=Path,required=True);p.add_argument('--expect-failure',action='store_true')
    a=p.parse_args();source=a.build.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    stage=out/'frontend-files';stage.mkdir()
    for f in (source/'frontend-files').iterdir():
        if f.is_dir():
            assert f.name=='maps';(stage/f.name).mkdir()
            for m in f.iterdir():
                if m.name.startswith('bloodgulch'):(stage/f.name/m.name).symlink_to(m.resolve())
        else:(stage/f.name).symlink_to(f.resolve())
    sdk=parse_args([]).sdk.resolve()/'bin';stripped=next(source.glob('*.stripped'));rom=out/'jackal-melee.z64'
    for command in [[sdk/'mkdfs',out/'frontend.dfs',stage],
        [sdk/'n64tool','--title','JACKAL MELEE QA','--toc','--output',rom,'--align','256',stripped,'--align','8',stripped.with_suffix('.sym'),'--align','16',out/'frontend.dfs'],
        [sdk/'ed64romconfig','--savetype','none','--regionfree','--controller1','n64','--controller2','n64','--controller3','n64','--controller4','n64',rom]]:
        subprocess.run(list(map(str,command)),check=True)
    assert rom.stat().st_size<64*1024*1024
    settings=a.settings.read_text();settings=re.sub(r'(?m)^  AutoSaveMemory:.*$','  AutoSaveMemory: false',settings)
    settings=re.sub(r'(?m)^  Mute:.*$','  Mute: true',settings);(out/'ares.bml').write_text(settings)
    with (out/'native.log').open('w') as log:
        proc=subprocess.Popen(['/Applications/ares.app/Contents/MacOS/ares','--settings-file',str(out/'ares.bml'),'--no-file-prompt',str(rom)],stdout=log,stderr=subprocess.STDOUT)
        try:
            started=time.monotonic();reported=0
            while proc.poll() is None and time.monotonic()-started<480:
                time.sleep(1);text=(out/'native.log').read_text(errors='replace')
                completed=len(re.findall(r'^JACKAL_MELEE PASS case=',text,re.M))
                if completed>=reported+8:reported=completed;print('Melee cases passed:',completed,flush=True)
                if re.search(r'assertion failed|CPU EXCEPTION',text,re.I) or 'JACKAL_MELEE_QA PASS' in text:break
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    text=(out/'native.log').read_text(errors='replace')
    failed=bool(re.search(r'assertion failed|CPU EXCEPTION',text,re.I))
    if a.expect_failure:
        assert failed and 'JACKAL_MELEE START case=0' in text and 'jackal->health==health' in text,text[-2500:]
        status='expected_regression_failure'
    else:
        assert not failed and 'JACKAL_MELEE_QA PASS cases=64' in text,text[-2500:]
        assert len(re.findall(r'^JACKAL_MELEE PASS case=',text,re.M))==64
        status='pass'
    result={'status':status,'rom_sha256':hashlib.sha256(rom.read_bytes()).hexdigest(),
        'stripped_sha256':hashlib.sha256(stripped.read_bytes()).hexdigest(),
        'native_log_sha256':hashlib.sha256((out/'native.log').read_bytes()).hexdigest(),
        'logging_caveat':'Identical executable and Blood Gulch inputs; other map payloads omitted only for Ares ISViewer.'}
    (out/'capture.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
