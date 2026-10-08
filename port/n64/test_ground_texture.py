"""Source blend, filter and 64px terrain wrap invariants."""
import unittest
import numpy as np
from PIL import Image
from extract_ground import compose,sample_repeat
from pack_terrain import indexed_terrain
class GroundTests(unittest.TestCase):
 def test_source_mask_endpoints_and_double_multiply(self):
  # Neutral micro map isolates source alpha: white=sand, black=grass.
  base=Image.new('RGBA',(4,4),(128,128,128,255));sand=Image.new('RGB',(4,4),(128,128,128));grass=Image.new('RGB',(4,4),(32,96,16));micro=Image.new('RGB',(4,4),(128,128,128))
  dirt=np.array(compose(base,sand,grass,micro,[100,60,12]))[0,0]
  base.putalpha(0);green=np.array(compose(base,sand,grass,micro,[100,60,12]))[0,0]
  np.testing.assert_array_equal(dirt,[129,129,129]);np.testing.assert_array_equal(green,[32,97,16])
 def test_bilinear_wrap_is_periodic(self):
  im=Image.fromarray(np.arange(4*4*3,dtype=np.uint8).reshape(4,4,3))
  uv=np.array([[-.3,.8],[0,1],[.125,.125]])
  np.testing.assert_allclose(sample_repeat(im,uv),sample_repeat(im,uv+[7,-3]))
 def test_64px_batch_offsets_preserve_full_period(self):
  a=(0,0,0,255,255,255,100001,-98300);b=(1,0,0,255,255,255,102800,-98300);c=(0,0,1,255,255,255,100001,-96400)
  batch=indexed_terrain([[a,b,c]],uv_period=2048)[0]
  shifted=[batch['vertices'][i] for i in batch['indices']]
  delta=[a[i]-shifted[0][i] for i in (6,7)]
  self.assertTrue(all(v%2048==0 for v in delta))
  for v,w in zip((a,b,c),shifted):self.assertEqual([v[i]-w[i] for i in (6,7)],delta)
if __name__=='__main__':unittest.main()
