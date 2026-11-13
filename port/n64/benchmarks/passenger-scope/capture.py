"""Capture native scope QA photos; run through tools/workspace.py run."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'port/n64'))
from build import parse_args
sys.path.insert(0,str(ROOT/'port/n64/benchmarks/firefight-limited'))
from decode_photo import decode


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--settings',type=Path,required=True)
    a=p.parse_args();source=a.build.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    stage=out/'frontend-files';stage.mkdir()
    for f in (source/'frontend-files').iterdir():
        if f.is_dir():
            assert f.name=='maps';(stage/f.name).mkdir()
            for m in f.iterdir():
                if m.name.startswith('bloodgulch'):(stage/f.name/m.name).symlink_to(m.resolve())
        else:(stage/f.name).symlink_to(f.resolve())
    sdk=parse_args([]).sdk.resolve()/'bin';stripped=next(source.glob('*.stripped'));rom=out/'scope-qa.z64'
    for command in [[sdk/'mkdfs',out/'frontend.dfs',stage],
        [sdk/'n64tool','--title','HALO SCOPE QA','--toc','--output',rom,'--align','256',stripped,'--align','8',stripped.with_suffix('.sym'),'--align','16',out/'frontend.dfs'],
        [sdk/'ed64romconfig','--savetype','none','--regionfree','--controller1','n64','--controller2','n64','--controller3','n64','--controller4','n64',rom]]:
        subprocess.run(list(map(str,command)),check=True)
    assert rom.stat().st_size<64*1024*1024
    settings=a.settings.read_text();settings=re.sub(r'(?m)^  AutoSaveMemory:.*$','  AutoSaveMemory: false',settings)
    settings=re.sub(r'(?m)^  Mute:.*$','  Mute: true',settings);(out/'ares.bml').write_text(settings)
    with (out/'native.log').open('w') as log:
        proc=subprocess.Popen(['/Applications/ares.app/Contents/MacOS/ares','--settings-file',str(out/'ares.bml'),'--no-file-prompt',str(rom)],stdout=log,stderr=subprocess.STDOUT)
        try:
            start=time.monotonic()
            while proc.poll() is None and time.monotonic()-start<240:
                time.sleep(1);text=(out/'native.log').read_text(errors='replace')
                if re.search('ASSERTION FAILED|CPU EXCEPTION',text):raise RuntimeError(text[-3000:])
                if 'M64_POLISH_QA PASS' in text:break
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    text=(out/'native.log').read_text(errors='replace');assert 'M64_POLISH_QA PASS' in text
    photos=re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END',text,re.S);assert len(photos)==15
    for photo in photos:
        page=int(re.search(r'tick=(\d+)',photo).group(1));raw=out/f'photo-{page}.log';raw.write_text(photo)
        decode(raw,out/f'photo-{page}.png')
    (out/'capture.json').write_text(json.dumps(dict(photos=len(photos),rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),
        stripped_sha256=hashlib.sha256(stripped.read_bytes()).hexdigest(),
        logging_caveat='Same executable/Blood Gulch inputs; other map filesystem payloads omitted only for ISViewer.'),indent=2)+'\n')


if __name__=='__main__':main()
