"""Directional visibility and self-occlusion in the model audit renderer."""
import unittest
import numpy as np
from audit_models import Mesh, render


class OcclusionTests(unittest.TestCase):
    def triangle(self, z=0, rgb=(230, 10, 20), reverse=False):
        p=np.array([[[-1.,-1,z],[1.,-1,z],[0.,1,z]]])
        if reverse:p=p[:,::-1]
        return Mesh(p,rgb=np.array([[rgb]*3]))

    def test_outward_face_visible_from_outside_only(self):
        mesh=self.triangle();bounds=(np.zeros(3),np.array([2.,2.]))
        _,front=render(mesh,bounds,(0,0,1),32,32)
        _,back=render(mesh,bounds,(0,0,-1),32,32)
        self.assertGreater(front.sum(),100)
        self.assertEqual(back.sum(),0)
        _,broken=render(mesh,bounds,(0,0,1),32,32,cull='front')
        self.assertEqual(broken.sum(),0)

    def test_nearest_surface_occludes_regardless_of_submission_order(self):
        front=self.triangle(.4);rear=self.triangle(0,(0,200,0))
        bounds=(np.zeros(3),np.array([2.,2.]))
        images=[]
        for a,b in ((front,rear),(rear,front)):
            mesh=Mesh(np.concatenate((a.p,b.p)),rgb=np.concatenate((a.rgb,b.rgb)))
            im,_=render(mesh,bounds,(0,0,1),32,32);images.append(np.asarray(im))
        np.testing.assert_array_equal(images[0],images[1])
        np.testing.assert_array_equal(images[0][16,16],(230,10,20))


if __name__=='__main__':unittest.main()
