"""Bounds must contain the exact packed positions and emitted float extrema."""
import math
import re
import struct
import unittest
import pack_bounds


class BoundsTests(unittest.TestCase):
    def test_quantized_animation_endpoints_and_interpolation(self):
        clips=[{'frames':[[[-.123, .25, .031]],[[.832, -.98, .72]]]},
               {'frames':[[[-.831, -.67, .19]],[[.429, .68, .34]]]}]
        box=pack_bounds.animation_bounds(*clips)
        for clip in clips:
            endpoints=[[round(v*128)/128 for v in pack_bounds.position(f[0],(0,0,0))] for f in clip['frames']]
            for weight in range(257):
                point=[(a*(256-weight)+b*weight)/256 for a,b in zip(*endpoints)]
                self.assertTrue(all(box[0][i]<=v<=box[1][i] for i,v in enumerate(point)))

    def test_near_far_union_radius_and_emitted_float(self):
        near={'triangles':[{'p':[[-.239,0,.49],[.539,.153,-.025],[.02,-.281,.19]]}]}
        far={'triangles':[{'p':[[.59,0,.51],[.61,.193,-.025],[.04,-.281,.19]]}]}
        boxes=[];radii=[]
        for model in (near,far):
            box,radius=pack_bounds.model_bounds(model,1024);boxes.append(box);radii.append(radius)
        box=pack_bounds.union(*boxes)
        emitted=[struct.unpack('f',struct.pack('f',float(v)))[0] for v in re.findall(r'[-+]?\d+\.\d+',pack_bounds.initializer(box))]
        for model in (near,far):
            for tri in model['triangles']:
                for source in tri['p']:
                    p=[round(v*1024)/1024 for v in pack_bounds.position(source,(0,0,0))]
                    self.assertTrue(all(emitted[i]<=p[i]<=emitted[3+i] for i in range(3)))
                    self.assertLessEqual(math.sqrt(sum(v*v for v in p)),max(radii))

    def test_reject_geometry_exceeding_fixed_matrix_margin(self):
        with self.assertRaises(ValueError):
            pack_bounds.model_bounds({'triangles':[{'p':[[100,100,100]]*3}]},1024)


if __name__=='__main__':unittest.main()
