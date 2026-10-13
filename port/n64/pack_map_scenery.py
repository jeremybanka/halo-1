"""Bake placed source scenery and its collision into new map banks."""
import math,struct,json
import numpy as np
from reclaimer.model.model_decompilation import extract_model
from pack_fp_ammo import globals_for

def rotation(row):
    yaw,pitch,roll=(row.rotation.y,row.rotation.p,row.rotation.r)
    cy,sy=math.cos(yaw),math.sin(yaw);cp,sp=math.cos(pitch),math.sin(pitch);cr,sr=math.cos(roll),math.sin(roll)
    return np.array([[cy,-sy,0],[sy,cy,0],[0,0,1]])@np.array([[cp,0,sp],[0,1,0],[-sp,0,cp]])@np.array([[1,0,0],[0,cr,-sr],[0,sr,cr]])

def append_collision(data,source,rot,pos,material_ids):
    planes,vertices,edges,surfaces=(len(data[k]) for k in ('planes','vertices','edges','surfaces'))
    for nx,ny,nz,d in source['planes']:
        normal=rot@np.array([nx,ny,nz]);data['planes'].append((*normal,float(d+normal@pos)))
    for x,y,z,edge in source['vertices']:
        point=rot@np.array([x,y,z])+pos;data['vertices'].append((*point,edge+edges))
    for v0,v1,e0,e1,s0,s1 in source['edges']:
        data['edges'].append((v0+vertices,v1+vertices,e0+edges,e1+edges,s0+surfaces if s0>=0 else -1,s1+surfaces if s1>=0 else -1))
    for plane,edge,flags,breakable,material in source['surfaces']:
        # Keep a signed 32-bit plane designator after adding the plane offset.
        designator=(plane&0x7fffffff)+planes
        if plane<0:designator-=0x80000000
        data['surfaces'].append((designator,edge+edges,flags,breakable,material_ids[material] if material>=0 else -1))

def scenery(halo,materials,data,collision_materials,add_triangle,include_lights=False):
    entries=halo.tag_index.tag_index;cache={};report=[]
    reduced_path=materials.directory.parent/'scenery-reduced.json'
    reduced=json.loads(reduced_path.read_text())['models'] if reduced_path.exists() else {}
    def meta(path,kind):
        i=next(i for i,e in enumerate(entries) if e.path==path and (kind is None or e.class_1.enum_name==kind))
        return halo.get_meta(i),i
    placements=[(p,halo.scnr_meta.sceneries_palette.STEPTREE[p.type].name.filepath,'scenery') for p in halo.scnr_meta.sceneries.STEPTREE]
    if include_lights:
        placements += [(p,halo.scnr_meta.light_fixtures_palette.STEPTREE[p.type].name.filepath,None) for p in halo.scnr_meta.light_fixtures.STEPTREE]
    for placement,path,kind in placements:
        if placement.not_placed.automatically:continue
        if path not in cache:
            obj,_=meta(path,kind)
            if not obj.obje_attrs.model.filepath:continue
            model,ix=meta(obj.obje_attrs.model.filepath,'model')
            halo.meta_to_tag_data(model,'mode',entries[ix]);candidates=extract_model(model,write_jms=False)
            candidates=[m for m in candidates if m.name.endswith(' superhigh')] or [m for m in candidates if m.tris]
            selected=candidates[min(max(0,placement.desired_permutation),len(candidates)-1)]
            mids=[materials.add(s.shader.filepath) for s in model.shaders.STEPTREE]
            nodes=[{'name':n.name,'parent':n.parent_index,'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w]} for n in selected.nodes]
            transforms=dict(zip([n['name'] for n in nodes],globals_for(nodes,nodes)))
            collision=None
            if obj.obje_attrs.collision_model.filepath:collision,_=meta(obj.obje_attrs.collision_model.filepath,'model_collision_geometry')
            cache[path]=(selected,mids,transforms,collision)
        model,mids,transforms,collision=cache[path];rot=rotation(placement);pos=np.array(list(placement.position));triangles=0
        proxy=reduced.get(path)
        if proxy:
            assert proxy['model']==model.name and proxy['source_triangles']==len(model.tris)
            source_vertices=[(*p,*uv) for p,uv in zip(proxy['vertices'],proxy['uv'])]
            source_faces=list(zip(proxy['faces'],proxy['materials']))
        else:
            source_vertices=[(v.pos_x/100,v.pos_y/100,v.pos_z/100,v.tex_u,v.tex_v) for v in model.verts]
            source_faces=[([t.v0,t.v1,t.v2],t.shader) for t in model.tris]
        for face,shader in source_faces:
            points=[]
            # JMS model faces have the opposite winding to BSP surface faces.
            for vi in reversed(face):
                v=source_vertices[vi];point=rot@np.array(v[:3])+pos
                points.append((*point,*v[3:]))
            add_triangle(mids[shader],points);triangles+=1
        collision_count=0
        if collision is not None:
            material_ids=[]
            for m in collision.materials.STEPTREE:
                material_ids.append(len(collision_materials));collision_materials.append(m.material_type.data)
            for node in collision.nodes.STEPTREE:
                r,t=transforms[node.name];world_rot=rot@r;world_pos=rot@t+pos
                for bsp in node.bsps.STEPTREE:
                    source={name:list(struct.iter_unpack('<'+fmt,bytes(getattr(bsp,name).STEPTREE))) for name,fmt in [('planes','4f'),('surfaces','2iBBh'),('edges','6i'),('vertices','3fi')]}
                    if source['surfaces']:
                        append_collision(data,source,world_rot,world_pos,material_ids);collision_count+=len(source['surfaces'])
        report.append({'path':path,'model':model.name,'triangles':triangles,'source_triangles':len(model.tris),'method':proxy['method'] if proxy else 'Original source geometry','collision_surfaces':collision_count,'position':list(pos),'rotation':list(placement.rotation),'source_kind':kind or 'light_fixture'})
    return report
