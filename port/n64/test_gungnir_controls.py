"""Preserve both production layouts and setup/HUD behavior under sanitizers."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def run(output):
    output.mkdir(parents=True,exist_ok=True);reports=[]
    for name,sources in [('controls',['controls.c']),('frontend',['frontend.c','menu.c','controls.c']),('menu',['menu.c','controls.c']),('hud_layout',[]),('damage_indicator',[])]:
        files=[ROOT/'port/n64'/('test_'+name+'.c'),*[ROOT/'port/n64'/n for n in sources]];binary=output/name
        command=['clang','-std=c17','-O1','-g','-fsanitize=address,undefined','-I'+str(ROOT/'port/n64'),*map(str,files),'-lm','-o',str(binary)];subprocess.run(command,cwd=ROOT,check=True)
        result=subprocess.run([str(binary.resolve())],cwd=ROOT,check=True,capture_output=True,text=True);(output/(name+'.log')).write_text(result.stdout+result.stderr);print(result.stdout.strip(),flush=True);reports.append(dict(name=name,source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},passed=True))
    (output/'checks.json').write_text(json.dumps(reports,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();run(a.output)
