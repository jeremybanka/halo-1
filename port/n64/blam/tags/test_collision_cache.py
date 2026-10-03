#!/usr/bin/env python3
"""Compare original Blam traversal against an independent polygon triangulation.

The reference fan uses the original collision edges/vertices, not the reduced
render mesh. Compiles the generated native C bank under ASan/UBSan and exercises
all player spawn locations plus seeded directional segments from those spawns.
"""
import argparse, contextlib, json, subprocess
from pathlib import Path
from export_collision import decode, check, polygons, number

ROOT = Path(__file__).resolve().parents[4]


def test(map_path, generated, output):
    output.mkdir(parents=True, exist_ok=True)
    with (output/'collision-test-decode.log').open('w') as log, contextlib.redirect_stdout(log):
        data, spawns = decode(map_path)
    topology = check(data)
    triangles = [(p[0],p[i],p[i+1],s) for s,p in enumerate(polygons(data)) for i in range(1,len(p)-1)]
    fixture = ['/* Generated local collision reference; do not commit. */',
               'static const float ref_vertices[][3]={']
    fixture += ['{'+','.join(number(v) for v in r[:3])+'},' for r in data['vertices']]
    fixture += ['};','static const int ref_triangles[][4]={']
    fixture += ['{'+','.join(map(str,r))+'},' for r in triangles]
    fixture += ['};','static const float ref_spawns[][3]={']
    fixture += ['{'+','.join(number(v) for v in r)+'},' for r in spawns]
    fixture += ['};']
    (output/'collision_reference.inc').write_text('\n'.join(fixture)+'\n')
    binary = output/'test_collision_cache'
    command = ['cc','-std=c11','-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer',
               '-I'+str(ROOT/'port/n64'),'-I'+str(ROOT/'build/n64/blam-core'),'-I'+str(output),
               str(Path(__file__).with_suffix('.c')),str(ROOT/'port/n64/blam/collision.c'),
               str(generated/'blam_collision_data.c'),'-lm','-o',str(binary)]
    subprocess.run(command,check=True,cwd=ROOT)
    result=subprocess.run([str(binary)],check=True,cwd=ROOT,text=True,capture_output=True)
    report={'topology':topology,'reference_triangles':len(triangles),'output':result.stdout.strip(),
            'validation':'ASan/UBSan; original polygon fan reference, not simplified map triangles'}
    (output/'collision-cache-test.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--map',type=Path,default=ROOT/'build/n64/assets/bloodgulch-decompressed.map')
    p.add_argument('--generated',type=Path,default=ROOT/'build/n64/generated')
    p.add_argument('--output',type=Path,default=ROOT/'build/n64/blam-tags')
    a=p.parse_args();test(a.map,a.generated,a.output)
