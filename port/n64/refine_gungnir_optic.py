"""Optic art direction: flat orange hex, charcoal housing and clean silver.

Keep the accepted convex helmet and every unrelated source surface. Only the
small optical component is replaced, using its original native head channel.
Original correspondence is retained as nearest source-face/barycentric data;
the enlarged geometry is explicitly recorded as a requested design change.
"""
import argparse,copy,hashlib,json,sys,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,interpolate
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_gungnir import bake


def run(source,motion,candidate,output):
    output.mkdir(parents=True,exist_ok=True)
    original=json.loads(source.read_text());data=json.loads((candidate/'solid.json').read_text());old=data['lods'][0]['triangles']
    lens=[t for t in old if t['component']=='helmet-lens'];anchor=np.array([t['p'] for t in lens]).mean((0,1));center=anchor.copy()
    radius=.006;half_width=.0089;half_height=math.sqrt(3)*radius*.65;housing_shift=-.18*(2*radius)
    faces=sorted({r['face'] for t in lens for r in t['source_faces']});tree=BVHTree.FromPolygons([Vector(p) for p in original['vertices']],[original['faces'][i] for i in faces],all_triangles=True)
    report=[]
    for lod,model in enumerate(data['lods']):
        before=[t for t in model['triangles'] if t['component']=='helmet-lens'];keep=[t for t in model['triangles'] if t['component']!='helmet-lens']
        shell=[t for t in model['triangles'] if t['component']=='helmet-shell'];shell_tree=BVHTree.FromPolygons([Vector(p) for t in shell for p in t['p']],np.arange(len(shell)*3).reshape(-1,3).tolist(),all_triangles=True)
        rectangle=[(center[1]+housing_shift+dy,center[2]+dz) for dy,dz in [(-half_width,-half_height),(half_width,-half_height),(half_width,half_height),(-half_width,half_height)]]
        hexagon=[(center[1]+radius*math.cos(i*math.pi/3),center[2]+radius*math.sin(i*math.pi/3)) for i in range(6)]
        hits=[]
        for y,z in [*rectangle,*hexagon]:
            hit=shell_tree.ray_cast(Vector((.2,y,z)),Vector((-1,0,0)))[0]
            assert hit is not None,'Optic must remain on the closed source helmet'
            hits.append(hit.x)
        frame_x=math.ceil((max(hits)+.0005)*512)/512;eye_x=frame_x+1/512
        def triangle(points,component,color):
            tri=dict(p=[list(p) for p in points],uv=[],weights=[],material=before[0]['material'],component=component,source_components=before[0]['source_components'],source_faces=[],construction='requested flat-topped hex optic and charcoal rectangular housing, fitted over the retained original convex helmet',color_override=color)
            for p in points:
                hit,_,fi,distance=tree.find_nearest(Vector(p));face=faces[fi];ids=original['faces'][face];bary=np.maximum(0,interpolate.poly_3d_calc([Vector(original['vertices'][i]) for i in ids],hit));bary/=bary.sum()
                tri['uv'].append((bary@np.array([original['uv'][i] for i in ids])).tolist());tri['weights'].append(copy.deepcopy(before[0]['weights'][0]));tri['source_faces'].append(dict(face=face,barycentric=bary.tolist(),surface_distance=distance,changed_topology=True,requested_optic_design_change=True,preserved_native_skin_channels=True))
            assert np.cross(np.subtract(points[1],points[0]),np.subtract(points[2],points[0]))[0]>0
            return tri
        frame=[(frame_x,y,z) for y,z in rectangle];eye=[(eye_x,y,z) for y,z in hexagon]
        replacement=[triangle([frame[i] for i in f],'helmet-optic-frame',[76,76,76]) for f in [(0,1,2),(0,2,3)]]
        replacement += [triangle([eye[i] for i in (0,j,j+1)],'helmet-lens',[255,149,25]) for j in range(1,5)]
        model['triangles']=keep+replacement
        frames,clips=bake(original,model['triangles'],motion);np.savez_compressed(output/f'poses-{lod}.npz',**frames);model['animations']=clips
        assert [t for t in model['triangles'] if not t['component'].startswith(('helmet-lens','helmet-optic-frame'))]==keep
        report.append(dict(lod=lod,parent_lens_triangles=len(before),new_lens_triangles=4,housing_triangles=2,frame_x=frame_x,eye_x=eye_x,minimum_quantized_layer_separation=1,orange_rgb=[255,149,25],housing_rgb=[76,76,76],helmet_shell_geometry_unchanged=True))
    data['optic_refinement']=dict(parent_sha256=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest(),art_anchor=anchor.tolist(),radius=radius,housing_half_width=half_width,housing_half_height=half_height,housing_lateral_offset=housing_shift,reference='User supplied orange flat-topped hexagon in charcoal rectangular housing, 2026-11-02',lods=report)
    data['publication_approved']=False
    (output/'solid.json').write_text(json.dumps(data,separators=(',',':'))+'\n');(output/'optic-refinement.json').write_text(json.dumps(data['optic_refinement'],indent=2)+'\n')
    print('OPTIC',report,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','motion','candidate','output'):p.add_argument(name,type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.motion,a.candidate,a.output)
