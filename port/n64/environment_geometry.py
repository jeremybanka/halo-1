"""Conform small BSP overlays to the simplified opaque surface, offline.

Clip in the overlay's source plane, retaining UV interpolation. Each resulting
triangle follows exactly one backing triangle rather than crossing the reduced
wall. No collision coordinates are changed.
"""
import numpy as np

RENDER_SCALE=256
OVERLAY_LIFT=8/RENDER_SCALE

def conform_overlays(triangles,materials):
    points=np.array([t['p'] for t in triangles],dtype=float)
    normals=np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0])
    normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
    result=[];counts={};max_distance=0.;minimum_coverage=1.
    for index,tri in enumerate(triangles):
        if tri['material'] not in materials:
            result.append(tri);continue
        p=points[index];n=normals[index]
        if materials[tri['material']]!='cap_moss01b':
            # Original light sheets vary slightly from the pylon plane. The
            # small outward clearance survives packing without subdividing
            # these tiny emissive faces.
            result.append({**tri,'p':(p-n*(8/RENDER_SCALE)).tolist()})
            counts[str(index)]=1
            continue
        u=p[1]-p[0];u/=np.linalg.norm(u);v=np.cross(n,u)
        basis=np.array([u,v]);local=(p-p[0])@basis.T
        uv=np.array(tri['uv']);transform=np.linalg.solve(np.c_[local,np.ones(3)],uv)
        # Source lights sit on the architectural wall; moss sits on cliff.
        # Exclude all translucent/special materials as possible receivers.
        candidates=np.where((normals@n>.6)&(np.min(np.abs((points-p[0])@n),axis=1)<1.0))[0]
        count=0;covered=0.
        for j in candidates:
            if triangles[j]['material']!=0:continue
            q=points[j];poly=[a.copy() for a in local]
            clip=(q-p[0])@basis.T
            # Sutherland-Hodgman, both source and receiver winding CCW.
            for a,b in zip(clip,np.roll(clip,-1,axis=0)):
                edge=b-a
                def side(x):return edge[0]*(x[1]-a[1])-edge[1]*(x[0]-a[0])
                old=poly;poly=[]
                if not old:break
                prev=old[-1];d0=side(prev)
                for cur in old:
                    d1=side(cur)
                    if (d0>=0)!=(d1>=0):poly.append(prev+(cur-prev)*(d0/(d0-d1)))
                    if d1>=0:poly.append(cur)
                    prev=cur;d0=d1
            if len(poly)<3:continue
            for k in range(1,len(poly)-1):
                xy=np.array([poly[0],poly[k],poly[k+1]])
                area=abs(np.linalg.det(np.array([xy[1]-xy[0],xy[2]-xy[0]])))/2
                if area<1e-7:continue
                xyz=p[0]+xy@basis
                distance=(xyz-q[0])@normals[j]/(n@normals[j])
                # Reject a different parallel wall behind the intended one.
                if np.max(np.abs(distance))>1.0:continue
                max_distance=max(max_distance,float(np.max(np.abs(distance))))
                xyz-=distance[:,None]*n
                # BSP normals face inward: offset toward the visible side.
                xyz-=normals[j]*OVERLAY_LIFT
                result.append({'material':tri['material'],'p':xyz.tolist(),
                               'uv':(np.c_[xy,np.ones(3)]@transform).tolist()})
                covered+=area;count+=1
        original_area=abs(np.linalg.det(np.array([local[1]-local[0],local[2]-local[0]])))/2
        minimum_coverage=min(minimum_coverage,covered/original_area)
        if not .80<=covered/original_area<=1.015:
            raise ValueError(f'Overlay {index}: receiver covers {covered/original_area:.3f} of source')
        counts[str(index)]=count
    return result,{'source_triangles':len(counts),'result_triangles':sum(counts.values()),
                   'max_projection_distance':max_distance,'lift':OVERLAY_LIFT,'minimum_moss_coverage':minimum_coverage}
