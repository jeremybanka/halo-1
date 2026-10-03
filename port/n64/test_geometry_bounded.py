"""Portable geometry safeguards for the deterministic distant-vehicle recipe."""
import copy
import unittest
from geometry_bounded import reduce_bounded, reduce_near_bounded, cross, sub, dot

class BoundedGeometryTest(unittest.TestCase):
    def fixture(self):
        points=[(0,0,0),(.001,0,0),(1,0,0),(1,1,0),(0,1,0)]
        faces=[(0,1,4),(1,3,4),(1,2,3)]
        model={'triangles':[{'p':[list(points[i]) for i in f],
            'uv':[[0,0],[1,0],[0,1]],'material':0,
            'weights':[[[0,1.]]]*3,'source_id':j} for j,f in enumerate(faces)]}
        original={'vertices':[(x,y,z) for x in (-1,1) for y in (-1,1) for z in (-1,1)]}
        return model,original

    def test_short_edge_is_bounded_deterministic_and_retains_winding(self):
        model,original=self.fixture();saved=copy.deepcopy(model)
        result,stats=reduce_bounded('ghost',model,original,{'max_pixel_displacement':.4})
        self.assertLess(len(result['triangles']),len(model['triangles']))
        self.assertEqual((result,stats),reduce_bounded('ghost',model,original,{'max_pixel_displacement':.4}))
        self.assertEqual(model,saved)
        self.assertLessEqual(stats['actual_max_world_displacement'],stats['world_displacement_limit'])
        for tri in result['triangles']:
            source=model['triangles'][tri['source_id']]
            a,b,c=source['p'];x,y,z=tri['p']
            self.assertGreater(dot(cross(sub(b,a),sub(c,a)),cross(sub(y,x),sub(z,x))),0)
            self.assertEqual(tri['uv'],source['uv'])
            self.assertEqual(tri['weights'],source['weights'])

    def test_protected_light_face_is_exact_and_prevents_collapse(self):
        model,original=self.fixture();model['triangles'][0]['material']=3
        result,stats=reduce_bounded('warthog',model,original,
            {'max_pixel_displacement':.6,'preserve_materials':[3]})
        self.assertEqual(result,model)
        self.assertEqual(stats['collapses'],0)

    def test_articulated_parts_do_not_share_collapse_clusters(self):
        model,original=self.fixture()
        wheel=copy.deepcopy(model['triangles'])
        for tri in wheel:
            tri['weights']=[[[14,1.]]]*3
            tri['p']=[[p[0],p[1],p[2]+.015] for p in tri['p']]
        model['triangles']+=wheel
        result,_=reduce_bounded('warthog',model,original,{'max_pixel_displacement':.6})
        body=[t for t in result['triangles'] if t['weights'][0][0][0]==0]
        tires=[t for t in result['triangles'] if t['weights'][0][0][0]==14]
        self.assertEqual(len(body),2);self.assertEqual(len(tires),2)
        self.assertTrue(all(p[2]==0 for t in body for p in t['p']))
        self.assertTrue(all(p[2]==.015 for t in tires for p in t['p']))

    def test_invalid_or_animated_use_is_rejected(self):
        model,original=self.fixture()
        for name,limit in [('spartan',.4),('ghost',0),('ghost',2)]:
            with self.assertRaises(ValueError):
                reduce_bounded(name,model,original,{'max_pixel_displacement':limit})

    def test_near_features_and_inputs_remain_exact(self):
        model,original=self.fixture();saved=copy.deepcopy(model)
        model['triangles'][0]['material']=1
        protected=copy.deepcopy(model)
        output,stats=reduce_near_bounded('ghost',model,original,
            {'max_world_displacement':.02,'preserve_materials':[1]})
        self.assertEqual(output,protected)
        self.assertTrue(stats['rigid_membership_preserved'])
        self.assertEqual(model,protected)
        output,stats=reduce_near_bounded('ghost',saved,original,
            {'max_world_displacement':.02})
        self.assertLess(len(output['triangles']),len(saved['triangles']))
        self.assertLessEqual(stats['actual_max_world_displacement'],.02)
        self.assertTrue(all('_bounded_source' not in t for t in output['triangles']))

if __name__=='__main__':unittest.main()
