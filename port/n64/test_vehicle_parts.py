"""Original Scorpion aim joints and rigid-part packing regression tests."""
import math
import unittest
from vehicle_parts import node_positions, split_vehicle, triangle_groups


class VehiclePartsTest(unittest.TestCase):
    def fixture(self):
        nodes=[{'name':str(i),'parent':-1,'p':[0,0,0],'q':[0,0,0,1]}
               for i in range(11)]
        nodes[7].update(parent=0,p=[0,0,1])
        nodes[8].update(parent=7,p=[.2,0,.3])
        nodes[9]['parent']=8;nodes[10]['parent']=8
        vertices=[];weights=[];tris=[]
        for bone in (0,7,8,9,10):
            points=[[bone,0,0],[bone+.1,0,0],[bone,.1,0]]
            vertices+=points;weights += [[bone,-1,0]]*3
            tris.append({'p':points,'uv':[[0,0]]*3,'material':0,'bone':bone})
        return {'triangles':tris},{'nodes':nodes,'vertices':vertices,'weights':weights}

    def test_turret_and_children_pitch_together(self):
        model,original=self.fixture()
        self.assertEqual(triangle_groups('scorpion',model,original),[0,1,2,2,2])
        ordered,rig=split_vehicle('scorpion',model,original)
        self.assertEqual([p['kind'] for p in rig['parts']],[0,2,3])
        pitch=rig['parts'][2]
        self.assertEqual(pitch['pivot'],[.2,1.3,0])
        faces=ordered['triangles'][pitch['first']//3:(pitch['first']+pitch['count'])//3]
        self.assertEqual({t['bone'] for t in faces if 'bone' in t},{8,9,10})
        self.assertEqual(sum(p['count'] for p in rig['parts']),len(ordered['triangles'])*3)
        self.assertTrue(all(p['count']%6==0 for p in rig['parts']))

    def test_inherited_joint_pivot_rotates_with_yaw(self):
        _,original=self.fixture()
        original['nodes'][7]['q']=[0,0,math.sin(math.pi/4),math.cos(math.pi/4)]
        pivot=node_positions(original['nodes'])[8]
        # Halo's stored node quaternion uses the conjugated rotation convention.
        for actual,expected in zip(pivot,[0,-.2,1.3]):
            self.assertAlmostEqual(actual,expected)


if __name__=='__main__':unittest.main()
