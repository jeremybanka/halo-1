"""Exercise the emitted scope bank at every integer interpolation fraction."""
import json
from pathlib import Path
import re
import unittest
import numpy as np
from pack_assets import position

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'build/n64/assets/firstperson-reduced.json'
GENERATED=ROOT/'build/n64/generated/firstperson_data.c'

@unittest.skipUnless(SOURCE.exists() and GENERATED.exists(), 'Requires owned first-person assets')
class ScopeGeometry(unittest.TestCase):
    def test_original_display_survives_all_animation_interpolations(self):
        weapon=json.loads(SOURCE.read_text())['weapons']['sniper']
        materials={i for i,n in enumerate(weapon['material_names']) if n.endswith((' screen',' subscreen'))}
        triangles=[i for i,t in enumerate(weapon['triangles']) if t['material'] in materials]
        self.assertEqual(len(triangles),4)
        text=GENERATED.read_text()
        encoded=re.search(r'bg_scope_poses\[\]\[12\]\[3\]=(.*?);',text).group(1)
        poses=np.array(json.loads(encoded.replace('{','[').replace('}',']')))
        offsets=[int(n) for n in re.search(r'bg_scope_offsets\[4\]=\{(.*?)\}',text).group(1).split(',')]
        checked=0
        for offset,clip in zip(offsets,weapon['clips'].values()):
            expected=np.array([[[round(v*4096) for v in position(p,(0,0,0))]
                                for i in triangles for p in frame[i*3:i*3+3]] for frame in clip['frames']])
            actual=poses[offset:offset+len(expected)]
            np.testing.assert_array_equal(actual,expected)
            for a,b in zip(actual[:-1],actual[1:]):
                for fraction in range(256):
                    # Match the signed integer interpolation in the real renderer.
                    p=(a+((b-a)*fraction>>8)).reshape(-1,3,3)
                    area=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
                    self.assertTrue(np.all(np.sum(area*area,axis=1)>0))
                    checked+=len(p)
        self.assertEqual(checked,18432)
        print(f'{checked} interpolated scope triangles retain nonzero area')

if __name__=='__main__':unittest.main()
