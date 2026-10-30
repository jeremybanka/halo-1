"""Blender entry point; source-color capture lives in the private archive.

Run from the repository root with Blender --background --python this_file.
The original two-tier models remain available in the previous archive.
"""
import sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'))
from reduce_pve_crunch import reduce
from symmetrize_pve import author
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'build/covenant-symmetry');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
p=args.output.resolve();p.mkdir(exist_ok=True,parents=True)
colors=p/'source-colors.json'
if not colors.exists():colors.write_bytes((ROOT/'halo64-assets/assets/covenant-symmetry/source-colors.json').read_bytes())
c=json.loads(colors.read_text());(p/'far-colors.json').write_text(json.dumps({n:v[1] for n,v in c.items()}))
reduce(ROOT/'halo64-assets/assets/covenant-crunch/reduced-source.json',p/'far-colors.json',p/'tuned-input.json',p/'head-tuning.blend',model_names=('grunt','jackal','hunter'),protect_heads=True,ratios={'grunt':.5,'jackal':.6,'hunter':.55},protect_arm_supports=True,protect_body_supports=True)
data=json.loads((p/'tuned-input.json').read_text())
for name in ('grunt','jackal','hunter'):
 g=data['models'][name]['source_geometry_lods']['n64 crunch'];c[name][2]=[[rgb+[t] for rgb,t in zip(cs,ts)] for cs,ts in zip(g['corner_colors'],g['corner_tints'])]
(p/'tuned-colors.json').write_text(json.dumps(c))
author(p/'tuned-input.json',p/'tuned-colors.json',p/'reduced-source.json',p/'symmetric.blend')
