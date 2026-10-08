"""Check packed surface orientation, occlusion clearance and unchanged collision."""
import json
from pathlib import Path
import unittest
import numpy as np
from environment_geometry import conform_overlays, RENDER_SCALE
from extract_environment_overlays import NAMES

ROOT=Path(__file__).resolve().parents[2]

class EnvironmentGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'build/n64/assets/bloodgulch-reduced.json').read_text())
        cls.overlays={i:m['name'].split('\\')[-1] for i,m in enumerate(cls.data['materials'])
                      if m['name'].split('\\')[-1] in NAMES}
        cls.before=cls.data['triangles']
        cls.after,cls.report=conform_overlays(cls.before,cls.overlays)

    def test_solid_geometry_and_collision_source_unchanged(self):
        self.assertEqual([t for t in self.before if t['material'] not in self.overlays],
                         [t for t in self.after if t['material'] not in self.overlays])
        self.assertEqual(self.data['triangles'],self.before)

    def test_no_packed_collapsed_or_reversed_faces(self):
        p=np.array([t['p'] for t in self.after]);q=np.round((p-[68,-118,0])*RENDER_SCALE)
        a=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);b=np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0])
        self.assertTrue(np.all((a*b).sum(1)>0))
        self.assertLessEqual(np.abs(q).max(),32767)
        # Eightfold finer storage, with no extra position bytes per vertex.
        self.assertLessEqual(np.abs(q/RENDER_SCALE+[68,-118,0]-p).max(),1/512)

    def test_overlay_samples_stay_in_front_of_packed_wall(self):
        solid=np.array([t['p'] for t in self.before if t['material'] not in self.overlays])
        solid=np.round((solid-[68,-118,0])*RENDER_SCALE)/RENDER_SCALE+[68,-118,0]
        normals=np.cross(solid[:,1]-solid[:,0],solid[:,2]-solid[:,0])
        normals/=np.linalg.norm(normals,axis=1)[:,None]
        count=0;minimum=100.
        for tri in self.after:
            if tri['material'] not in self.overlays:continue
            p=np.round((np.array(tri['p'])-[68,-118,0])*RENDER_SCALE)/RENDER_SCALE+[68,-118,0]
            n=np.cross(p[1]-p[0],p[2]-p[0]);n/=np.linalg.norm(n)
            for weights in ((1/3,1/3,1/3),(.6,.2,.2),(.2,.6,.2),(.2,.2,.6)):
                point=np.array(weights)@p;distance=(solid[:,0]-point)@n
                candidates=np.where((normals@n>.9)&(abs(distance)<.10))[0]
                matches=[]
                for j in candidates:
                    a,b,c=solid[j];ray=(a-point)@normals[j]/(n@normals[j])
                    hit=point+ray*n
                    uv=np.linalg.lstsq(np.array([b-a,c-a]).T,hit-a,rcond=None)[0]
                    if min(uv)>=-1e-5 and sum(uv)<=1.00001:matches.append(ray)
                if not matches:continue  # Quantized receiver edge / pylon border.
                clearance=min(matches,key=abs);minimum=min(minimum,clearance);count+=1
                self.assertGreater(clearance,.003, 'Overlay intersects its depth-tested receiver')
        self.assertGreater(count,250)
        print(f'{count} independent packed overlay/wall probes; minimum clearance {minimum:.6f}')

if __name__=='__main__':unittest.main()
