"""Focused controls/HUD regression tests, with address/undefined sanitizers."""
import subprocess,os,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;OUT=ROOT/'build/m64-polish/host';OUT.mkdir(parents=True,exist_ok=True)
checks={'controls':['controls.c'],'menu':['menu.c','controls.c'],'frontend':['frontend.c','menu.c','controls.c'],'menu_qa':['menu_qa.c','menu.c','controls.c'],'hud_layout':[],'damage_indicator':[]}
report={}
for name,sources in checks.items():
 paths=[ROOT/'port/n64'/('test_'+name+'.c'),*[ROOT/'port/n64'/s for s in sources]]
 command=['clang','-std=c17','-O1','-g','-fsanitize=address,undefined','-I'+str(ROOT/'port/n64'),*map(str,paths),'-lm','-o',str(OUT/name)]
 subprocess.run(command,cwd=ROOT,check=True)
 result=subprocess.run([str(OUT/name)],cwd=ROOT,check=True,capture_output=True,text=True)
 (HERE/(name+'.log')).write_text(result.stdout+result.stderr);print(result.stdout.strip())
 report[name]={'pass':True,'command':command,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
(HERE/'controls-host.json').write_text(json.dumps(report,indent=2)+'\n')
