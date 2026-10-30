"""Run current gameplay/UI checks without overwriting historical appraisal logs."""
import hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).parent;OUT=ROOT/'build/firefight-checkpoint'
OUT.mkdir(parents=True,exist_ok=True)
# Reuse the existing reviewed harnesses; only redirect their evidence/output paths.
for name in ('test_controls.py','test_game.py'):
 source=ROOT/'port/n64/benchmarks/m64-polish'/name
 code=source.read_text().replace("HERE=Path(__file__).resolve().parent;OUT=ROOT/'build/m64-polish/host'",f"HERE=Path({str(HERE)!r});OUT=ROOT/'build/firefight-checkpoint/host'")
 assert code!=source.read_text()
 exec(compile(code,str(source),'exec'),{'__file__':str(source),'__name__':'__main__'})
for name,extra in [('scope_mask',[]),('scope_depth',[]),('view_camera',['build/n64/generated/camera_data.c'])]:
 command=['clang','-std=c17','-O1','-g','-fsanitize=address,undefined','-Iport/n64','port/n64/test_'+name+'.c',*extra,'-lm','-o',str(OUT/name)]
 subprocess.run(command,cwd=ROOT,check=True)
 result=subprocess.run([str(OUT/name)],cwd=ROOT,text=True,capture_output=True,check=True)
 (HERE/(name+'.log')).write_text(result.stdout+result.stderr);print(result.stdout.strip(),flush=True)
# Latest native release and QA binaries already passed; certify their actual inputs.
verified={}
for case in ('after','play'):
 path=next((ROOT/'build/scope-fix'/case).glob('*.build.json'));m=json.loads(path.read_text());inputs=0
 for group in ('sources','headers','included_data','generated_adapters'):
  for name,want in m[group].items():
   p=ROOT/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==want,(case,group,name);inputs+=1
 rom=Path(m['rom']['path']);assert hashlib.sha256(rom.read_bytes()).hexdigest()==m['rom']['sha256']
 verified[case]={'manifest_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'compiler_inputs':inputs,'rom':m['rom']}
config=ROOT/'build/scope-fix/config.log';assert 'PASS: 47 configurations / 188 target translation units' in config.read_text()
(HERE/'runtime-configurations.log').write_bytes(config.read_bytes())
(HERE/'verified-builds.json').write_text(json.dumps(verified,indent=2)+'\n')
print('PASS current native release/QA compiler inputs, ROM hashes and 47 configuration record',flush=True)
