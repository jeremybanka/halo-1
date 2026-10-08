"""Exercise actual emitted thin-meter geometry through integer interpolation."""
import json,re,unittest
from pathlib import Path
import numpy as np
from pack_firstperson import split_details
from pack_assets import position

ROOT=Path(__file__).resolve().parents[2]
A=ROOT/'build/n64/assets';G=ROOT/'build/n64/generated'

@unittest.skipUnless((A/'firstperson-reduced.json').exists(),'Requires owned assets')
class PlasmaMeters(unittest.TestCase):
    def test_emitted_displays_survive_every_interpolation_fraction(self):
        data=json.loads((A/'firstperson-reduced.json').read_text())
        text=(G/'firstperson_data.c').read_text();checked=0
        for name in ('plasma_pistol','plasma_rifle'):
            w=data['weapons'][name];body,keep,sources,indices=split_details(w,name)
            self.assertEqual(len(indices)//3,6 if name=='plasma_pistol' else 2)
            self.assertLessEqual(len(sources),12)
            self.assertEqual(len(body['triangles'])+len(indices)//3,len(w['triangles']))
            prefix='bg_detail_'+name
            value=re.search(prefix+r'_poses\[\]\[\d+\]\[3\]=(.*?);',text).group(1)
            poses=np.array(json.loads(value.replace('{','[').replace('}',']')))
            offsets=list(map(int,re.search(prefix+r'_offsets\[4\]=\{(.*?)\}',text).group(1).split(',')))
            for offset,clip in zip(offsets,w['clips'].values()):
                expected=np.array([[[round(x*4096) for x in position(f[i],(0,0,0))]
                                    for i in sources] for f in clip['frames']])
                actual=poses[offset:offset+len(expected),:len(sources)]
                np.testing.assert_array_equal(actual,expected)
                for a,b in zip(actual[:-1],actual[1:]):
                    for fraction in range(256):
                        p=(a+((b-a)*fraction>>8))[indices].reshape(-1,3,3)
                        area=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
                        self.assertTrue(np.all(np.sum(area*area,axis=1)>0),(name,fraction))
                        checked+=len(p)
        print(f'{checked} plasma display interpolation samples retain nonzero area')

    def test_ready_display_banks_match_the_render_vertex_counts(self):
        text=(G/'interaction_assets.c').read_text()
        rows=re.search(r'bg_ready_plasma\[2\]=\{(.*?)\};',text).group(1)
        defs=re.findall(r'\{(\d+),(\d+),(\d+),(\d+),',rows)
        data=json.loads((A/'firstperson-reduced.json').read_text())
        bank=(ROOT/'build/n64/frontend-files/interactions.bin').read_bytes()
        for name,row in zip(('plasma_pistol','plasma_rifle'),defs):
            offset,stride,vertices,frames=map(int,row)
            _,_,sources,indices=split_details(data['weapons'][name],name)
            self.assertEqual(vertices,len(sources));self.assertGreater(frames,1)
            poses=np.array([np.frombuffer(bank,dtype='>i2',count=vertices*3,offset=offset+i*stride).reshape(vertices,3) for i in range(frames)])
            for a,b in zip(poses.astype(int)[:-1],poses.astype(int)[1:]):
                for fraction in range(256):
                    p=(a+((b-a)*fraction>>8))[indices].reshape(-1,3,3)
                    self.assertTrue(np.all(np.any(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1)))
        self.assertEqual(len(defs),2)

if __name__=='__main__':unittest.main()
