"""Retain CE vehicle movement selection and required math, with audited services."""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent/'blam'))
from prepare_vehicle import function,adapt
OUT=ROOT/'build/pve-vehicles/bank'
def prepare():
 funcs={};records=[]
 for path,names in {'source/ai/actor_moving.c':['actor_move_calculate_movement','actor_move_calculate_controlled_by_aiming','actor_move_calculate_free'],'source/units/bipeds.c':['biped_build_flying_axes']}.items():
  source=(ROOT/path).read_text()
  for name in names:
   s=function(source,name);funcs[name]=adapt(s);records.append({'path':path,'name':name,'function_sha256':hashlib.sha256(s.encode()).hexdigest()})
 sources=[(p,(ROOT/p).read_text()) for p in ['source/math/real_math.h','source/math/real_math.c','source/math/matrix_math.c']]
 seen=set(funcs);queue=list(funcs.values())
 while queue:
  for name in re.findall(r'\b(\w+)\s*\(',queue.pop()):
   if name in seen or name.startswith(('match_assert','assert_valid','valid_real')):continue
   seen.add(name)
   for path,source in sources:
    try:s=function(source,name)
    except RuntimeError:continue
    if '__asm' in s:raise ValueError(name)
    funcs[name]=adapt(s);queue.append(s);records.append({'path':path,'name':name,'function_sha256':hashlib.sha256(s.encode()).hexdigest()});break
 protos=[s[:s.index('{')].strip()+';' for s in funcs.values()]
 (OUT/'enemy_vehicle_ai_original.inc').write_text('/* Original CE bodies; engine services supplied by vehicle_ai.c. */\n'+'\n'.join(protos)+'\n'+'\n'.join(funcs.values()))
 (OUT/'ai-source-manifest.json').write_text(json.dumps({'functions':records,'adaptation':'Xbox long is int32_t; inline spelling only. Grid/clearance, actor records and stopping-distance inputs at explicit platform boundary.'},indent=2))
 print(len(funcs),'original functions')
if __name__=='__main__':prepare()
