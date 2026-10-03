"""Verify source ammo semantics and ownership against the actual owned bank."""
import json
from pathlib import Path
import re
import unittest
from pack_fp_ammo import prepare_ar, prepare_needler
from pack_firstperson import prepare_model

ASSETS=Path('build/n64/assets')


@unittest.skipUnless((ASSETS/'firstperson-ammo.json').exists(), 'Owned Xbox FP ammo extraction required')
class FirstpersonAmmoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=json.loads((ASSETS/'firstperson-raw.json').read_text())
        cls.reduced=json.loads((ASSETS/'firstperson-reduced.json').read_text())
        cls.meta=json.loads((ASSETS/'firstperson-ammo.json').read_text())
        cls.ar=prepare_ar(cls.reduced,cls.meta)
        cls.needle=prepare_needler(cls.raw,cls.reduced,cls.meta)

    def test_original_numeric_shader_contract(self):
        self.assertEqual([m['permutation'] for m in self.meta['ar']['materials']],[1,0])
        self.assertTrue(all(m['limit']==60 and len(m['textures'])==10 for m in self.meta['ar']['materials']))
        self.assertEqual(len(self.ar['corners']),8)
        self.assertEqual([len(f) for f in self.ar['poses']],[4,4,8,6])
        self.assertEqual(len(self.ar['pixels'])*2,3200)
        self.assertTrue(all(-32768<=v<=32767 for clip in self.ar['poses'] for frame in clip for point in frame for v in point))

    def test_native_overlay_not_synthetic_first_frame(self):
        frames=self.meta['needler']['frames']
        self.assertEqual(len(frames),21)
        names=self.raw['weapons']['needler']['nodes']
        needles=[i for i,n in enumerate(names) if 'needle' in n['name']]
        self.assertEqual(len(needles),16)
        self.assertTrue(all(sum(v*v for v in frames[0][i]['q'][:3])>.2 for i in needles))
        self.assertTrue(all(sum(v*v for v in frames[20][i]['q'][:3])==0 for i in needles))
        magnitudes={sum(v*v for v in frame[i]['q'][:3]) for frame in frames for i in needles}
        self.assertTrue(all(v==0 or v>=.285 for v in magnitudes))
        self.assertEqual(self.needle['visible_crystals'][0],0)
        self.assertEqual(self.needle['visible_crystals'][20],16)

    def test_actual_bank_mapping_and_rigid_folded_components(self):
        w=self.reduced['weapons']['needler'];mesh,_,_=prepare_model(w,'needler')
        text=Path('build/n64/generated/firstperson_data.c').read_text()
        record=re.search(r'\{fp_needler,(\d+),',text)
        self.assertEqual(int(record[1]),self.needle['base_vertices'])
        self.assertEqual(len(mesh['sources']),self.needle['base_vertices'])
        per_vertex=dict(zip(self.needle['vertices'],self.needle['bones']))
        corners=[]
        for first,_,start,count in mesh['batches']:
            corners.extend(first+i for i in mesh['indices'][start:start+count])
        for i in range(0,len(corners),3):
            bones=[per_vertex.get(v) for v in corners[i:i+3]]
            if any(b is not None for b in bones):
                self.assertEqual(len(set(bones)),1)
                # Every fully folded triangle has exactly coincident points
                # at ALL four clips' endpoints, not merely the idle pose.
                ids=[self.needle['vertices'].index(v) for v in corners[i:i+3]]
                tracks=[self.needle['indices'][v] for v in ids] # ammo0
                for f in range(self.needle['frames']):
                    points=[tuple(self.needle['values'][(f*self.needle['tracks']+t)*3+a] for a in range(3)) for t in tracks]
                    self.assertEqual(len(set(points)),1)

    def test_counter_is_in_all_four_idle_fire_viewports(self):
        import math
        focal=60/math.tan(1.08/2)
        for center in [(91,68),(69,68),(91,52),(69,52)]:
            for clip in self.ar['poses'][:2]:
                for frame in clip:
                    for x,y,z in frame:
                        self.assertGreater(x/4096,1.4/32)
                        px=center[0]+z/x*focal;py=center[1]-y/x*focal
                        self.assertTrue(0<px<160 and 0<py<120)


if __name__=='__main__':unittest.main()
