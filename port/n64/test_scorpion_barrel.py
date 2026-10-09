"""The visibility repair must stay closed, rigid and bounded, with a real sleeve."""
import copy
import math
import unittest
from collections import Counter
from scorpion_barrel import replace_cannon
from model_colors import bake_triangle
from PIL import Image

class CannonTest(unittest.TestCase):
    def fixture(self):
        original={'nodes':[{'name':'root','parent':-1,'p':[0,0,0],'q':[0,0,0,1]},
                           {'name':'frame cannon','parent':0,'p':[.4,0,1.2],'q':[0,0,0,1]}]}
        triangles=[]
        for mat,x0,x1 in [(0,.4,1.5),(1,.7,.95),(1,1.5,1.5)]:
            triangles.append({'p':[[x0,-.05,1.15],[x1,.05,1.15],[x1,0,1.25]],
                              'uv':[[.1,.1],[.8,.1],[.5,.8]],'material':mat,
                              'weights':[[[1,1.0]]]*3,'part':3})
        triangles.append({'p':[[0,0,0],[1,0,0],[0,1,0]],'uv':[[0,0]]*3,'material':0,
                          'weights':[[[0,1.0]]]*3,'part':0})
        model={'triangles':triangles,'textures':[None,None],'material_colors':[[30,30,25],[130,120,95]]}
        return model,original,{'root_cross_section':[.18,.14],'muzzle_cross_section':[.14,.12],'housing_overlap':.35}

    def test_closed_inward_shell_and_exact_muzzle(self):
        model,original,settings=self.fixture();before=copy.deepcopy(model)
        out=replace_cannon(model,original,model,settings);shell=out['triangles'][1:]
        self.assertEqual(model,before);self.assertEqual(out['triangles'][0],model['triangles'][-1]);self.assertEqual(len(shell),28)
        edges=Counter();points=set();center=[.8,0,1.2];volume=0
        for t in shell:
            p=t['p'];self.assertEqual(t['weights'],[[[1,1.0]]]*3)
            for i in range(3):edges[tuple(sorted((tuple(p[i]),tuple(p[(i+1)%3]))))]+=1;points.add(tuple(p[i]))
            u=[p[1][i]-p[0][i]for i in range(3)];v=[p[2][i]-p[0][i]for i in range(3)];n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            self.assertGreater(sum(n[i]*(center[i]-p[0][i])for i in range(3)),0)
        self.assertEqual(set(edges.values()),{2});self.assertEqual(len(points),16)
        self.assertEqual(max(p[0]for p in points),1.5)
        self.assertAlmostEqual(min(p[0]for p in points),.05)

    def test_source_sleeve_colors_and_idempotence_guard(self):
        model,original,settings=self.fixture();out=replace_cannon(model,original,model,settings)
        side=out['triangles'][5:]
        self.assertEqual({t['material'] for t in side},{0,1})
        self.assertTrue(all(t['sample_uv_direct'] for t in side))
        self.assertGreater(max(c[0] for t in side if t['material']==1 for c in bake_triangle(t,[None,None],out)),
                           max(c[0] for t in side if t['material']==0 for c in bake_triangle(t,[None,None],out)))
        self.assertTrue(all(all(0<=v<=255 for c in bake_triangle(t,[None,None],out)for v in c)for t in side))
        with self.assertRaises(ValueError):replace_cannon(out,original,model,settings)

    def test_reject_mixed_rig_and_invalid_colors(self):
        model,original,settings=self.fixture();model['triangles'][0]['weights'][0]=[[1,.5],[0,.5]]
        with self.assertRaises(ValueError):replace_cannon(model,original,model,settings)
        with self.assertRaises(ValueError):bake_triangle({'material':0,'sample_uv_direct':True,'uv':[[math.nan,0]]*3},[],{})

    def test_direct_uv_samples_do_not_blend_atlas_regions(self):
        image=Image.new('RGB',(8,8),(0,0,0))
        image.putpixel((0,0),(200,100,50))
        image.putpixel((7,0),(50,200,100))
        image.putpixel((0,7),(100,50,200))
        tri={'p':[[0,0,0],[1,0,0],[0,1,0]],'uv':[[.01,.01],[.99,.01],[.01,.99]],
             'material':0,'sample_uv_direct':True}
        rgb=bake_triangle(tri,[image],{})
        self.assertEqual([max(range(3),key=c.__getitem__)for c in rgb],[0,1,2])
        self.assertGreater(min(max(c)for c in rgb),100)
        # The default broad-face sampler deliberately remains distinct.
        del tri['sample_uv_direct']
        self.assertNotEqual(rgb,bake_triangle(tri,[image],{}))

if __name__=='__main__':unittest.main()
