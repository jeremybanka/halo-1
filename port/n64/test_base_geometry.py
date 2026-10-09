"""Owned BSP regression: exact architecture, sealed joins, runtime floor probes."""
from collections import Counter
import json
from pathlib import Path
import subprocess
import unittest
from pack_assets import normal, position
from test_render_matrix import function

ROOT=Path(__file__).resolve().parents[2]
ASSETS=ROOT/'build/n64/assets'

@unittest.skipUnless((ASSETS/'bloodgulch-raw.json').exists(), 'Requires owned BSP extraction')
class BaseGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=json.loads((ASSETS/'bloodgulch-raw.json').read_text())
        cls.out=json.loads((ASSETS/'bloodgulch-reduced.json').read_text())
        cls.materials=set(cls.out['architecture_materials'])
        cls.original=[{'p':[g['vertices'][i] for i in f],
                       'uv':[g['uv'][i] for i in f], 'material':g['material']}
                      for g in cls.raw['groups'] if g['material'] in cls.materials for f in g['faces']]

    def test_architecture_preserves_every_source_corner_uv_and_face(self):
        self.assertEqual([t for t in self.out['triangles'] if t['material'] in self.materials],self.original)
        self.assertEqual(len(self.original),1688)

    def test_all_landscape_boundary_vertices_are_pinned(self):
        key=lambda p:tuple(round(v,4) for v in p)
        edges=Counter()
        for g in self.raw['groups']:
            if g['material'] in self.materials:continue
            for face in g['faces']:
                p=[key(g['vertices'][i]) for i in face]
                for i in range(3):edges[tuple(sorted((p[i],p[(i+1)%3])))]+=1
        boundary={p for edge,n in edges.items() if n==1 for p in edge}
        vertices={key(p) for t in self.out['triangles'] if t['material'] not in self.materials for p in t['p']}
        self.assertGreater(len(boundary),100)
        self.assertFalse(boundary-vertices, 'A displaced BSP join exposes sky below a ramp')

    def test_runtime_collision_supports_original_ramps_and_floors(self):
        # Run the actual grid lookup/floor implementation against the generated
        # collision bank. Probe the centroid of every source walkable face.
        probes=[]
        for t in self.original:
            p=[position(v) for v in t['p']]
            if normal(p)[1]**2<.38:continue
            probes.append([sum(v[a] for v in p)/3 for a in range(3)])
        out=ROOT/'build/n64/geometry-audit/floor-test';out.mkdir(parents=True,exist_ok=True)
        source=(ROOT/'port/n64/game.c').read_text()
        c='#include <math.h>\n#include <assert.h>\n#include <stdbool.h>\n#include <stdint.h>\n#include <string.h>\n#include <stdio.h>\n#include "world.h"\n'
        for name,decl in [('sub','static void sub(float*d,const float*a,const float*b)'),
                          ('dot','static float dot(const float*a,const float*b)'),
                          ('cross','static void cross(float*d,const float*a,const float*b)'),
                          ('cell','static int cell(float x,float z)'),
                          ('floor_uncached','static float floor_uncached(float x,float z,float ceiling)'),
                          ('bg_floor','float bg_floor(float x,float z,float ceiling)')]:
            c+=decl+'{'+function(source,name)+'}\n'
        c+='static const float probes[][3]={'+','.join('{'+','.join(f'{x:.9f}f' for x in p)+'}' for p in probes)+'};\n'
        c+='int main(void){for(unsigned i=0;i<sizeof(probes)/sizeof(probes[0]);i++){const float*p=probes[i];float y=bg_floor(p[0],p[2],p[1]+.0005f);assert(fabsf(y-p[1])<.001f);}printf("%zu original architecture floor probes passed\\n",sizeof(probes)/sizeof(probes[0]));}\n'
        (out/'test.c').write_text(c)
        subprocess.run(['cc','-std=c17','-O2','-I'+str(ROOT/'port/n64'),str(out/'test.c'),str(ROOT/'build/n64/generated/collision_data.c'),'-lm','-o',str(out/'test')],check=True)
        subprocess.run([str(out/'test')],check=True)

if __name__=='__main__':unittest.main()
