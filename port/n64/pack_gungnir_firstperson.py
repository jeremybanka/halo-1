"""Bind GUNGNIR's original plates to the existing animated CE hand mesh.

An affine skin constraint recovers both forearm frames from existing hand vertices.
This follows every production ready/service/reload pose without another bank
of per-frame meshes. The CE rubber sleeve/glove remains the continuous backing.
"""
import json, hashlib
from pathlib import Path
import numpy as np
from pack_firstperson import prepare_model, split_details
from pack_mesh import indexed_mesh, emit_batches
from pack_assets import position
from gungnir_assets import texture_path

ROOT=Path(__file__).resolve().parents[2];A=ROOT/'halo64-assets';OUT=None
SOURCE=None
GENERATED=None

def globals_for(nodes):
    result=[None]*len(nodes)
    def visit(i):
        if result[i] is not None:return result[i]
        n=nodes[i]
        x,y,z,w=np.array(n['q'])*np.array((-1,-1,-1,1));m=np.eye(4)
        m[:3,:3]=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                  [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                  [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
        m[:3,3]=n['p'];result[i]=visit(n['parent'])@m if n['parent']>=0 and n['parent']!=i else m
        return result[i]
    for i in range(len(nodes)):visit(i)
    return np.array(result)

def basis(a,b,width):
    x=b-a;x/=np.linalg.norm(x);y=width-x*np.dot(width,x);y/=np.linalg.norm(y)
    return np.stack((x,y,np.cross(x,y)),axis=1)

def source_plates():
    from pack_gungnir import corner_colors,prepare_broad_colors
    from extract_gungnir import bone_globals
    from PIL import Image
    data=json.loads(SOURCE.read_text());nodes=data['nodes'];bind=bone_globals(nodes);lookup={n['name']:i for i,n in enumerate(nodes)}
    rotate=np.array(((0,1,0),(-1,0,0),(0,0,1)));bones={};width_axes={}
    for side in ('l','r'):
        elbow=bind[lookup[f'b_{side}_forearm']][:3,3];wrist=bind[lookup[f'b_{side}_hand']][:3,3];width=bind[lookup[f'b_{side}_hand']][:3,1]
        if abs(np.dot(width,(wrist-elbow)/np.linalg.norm(wrist-elbow)))>.8:width=bind[lookup[f'b_{side}_hand']][:3,2]
        width_axes[side]=(width*.04).tolist()
        for name,p in [('forearm',elbow),('hand',wrist)]:
            matrix=np.eye(4);matrix[:3,3]=p@rotate*3.048;bones[f'b_{side}_{name}']=matrix.tolist()
    textures={i:Image.open(texture_path(p,SOURCE)).convert('RGB') for i,p in enumerate(data['textures']) if p};prepare_broad_colors(data,textures);components=[]
    for component in ('left-forearm','right-forearm','wrist-buckler'):
        tris=[t for t in data['lods'][0]['triangles'] if t['component']==component];vertices=[];weights=[];colors=[];faces=[]
        for t in tris:
            faces.append(list(range(len(vertices),len(vertices)+3)))
            for p,ws in zip(t['p'],t['weights']):
                vertices.append((np.array(p)@rotate*3.048).tolist());dominant=max(ws,key=lambda x:x[1])[0];side='l' if '_l_' in nodes[dominant]['name'] else 'r';weights.append([[f'b_{side}_forearm',1]])
            rgb,_=corner_colors(t,data['materials'],textures);colors.extend((np.array(rgb)/255).tolist())
        components.append(dict(component=component,vertices=vertices,faces=faces,weights=weights,colors=colors))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'firstperson-plates.json').write_text(json.dumps(dict(bones=bones,width_axes=width_axes,components=components,source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),fit='Own Reach forearm guards and wrist buckler; CE anatomical cage, continuous articulated CE gloves')))


def run():
    source_plates()
    raw=json.loads((A/'assets/firstperson-raw.json').read_text());reduced=json.loads((A/'assets/firstperson-reduced.json').read_text())
    plate=json.loads((OUT/'firstperson-plates.json').read_text());hn=raw['hands']['nodes'];hb=globals_for(hn)
    hi={n['name']:i for i,n in enumerate(hn)};ar=raw['weapons']['ar'];lookup={n['name']:i for i,n in enumerate(ar['nodes'])}
    pose=globals_for([{**n,**s} for n,s in zip(ar['nodes'],ar['clips']['idle']['frames'][0])])
    skin=np.array([pose[lookup[n['name']]]@np.linalg.inv(hb[i]) for i,n in enumerate(hn)])
    w=reduced['weapons']['ar'];hand=w['triangles'][:w['hand_triangle_count']]
    corners=[];weights=[];representatives=[];seen=set()
    for i,(p,ws) in enumerate((p,ws) for t in hand for p,ws in zip(t['p'],t['weights'])):
        mat=sum(skin[b]*v for b,v in ws);bind=(np.linalg.inv(mat)@[*p,1])[:3]
        key=(tuple(np.round(bind,6)),tuple((b,round(v,6)) for b,v in ws))
        if key not in seen:
            seen.add(key);corners.append(bind);weights.append(dict(ws));representatives.append(i)
    corners=np.array(corners)
    bindings=[];joint_ids=[];report={'method':'Exact affine skin constraint on CE hand vertices; native GUNGNIR forearm plates with articulated CE glove backing','bones':[],'weapons':{}}
    for side in ('l','r'):
        for part in ('forearm',):
            bone=hi[f'frame {side} {part}'];allowed={bone} if part=='forearm' else {bone,hi[f'frame {side} forearm']}
            ids=[i for i,ws in enumerate(weights) if set(ws)<=allowed]
            ordered=sorted(allowed);design=np.concatenate([np.array([[*corners[i],1] for i in ids]).T*np.array([weights[i].get(b,0) for i in ids])[None,:] for b in ordered],axis=0)
            origin=hb[bone,:3,3];proxy=np.array([origin,origin+[.08,0,0],origin+[0,.08,0],origin+[0,0,.08]])
            target=np.zeros((len(ordered)*4,4));target[ordered.index(bone)*4:ordered.index(bone)*4+4]=np.column_stack((proxy,np.ones(4))).T
            coeff=np.linalg.lstsq(design,target,rcond=1e-7)[0].T
            coeff/=coeff.sum(axis=1)[:,None]
            error=float(np.max(np.abs(design@coeff.T-target)))
            assert error<1e-6,(side,part,error)
            assert np.abs(coeff).sum(1).max()<8,(side,part)
            bindings.append({'corners':[representatives[i] for i in ids],'coeff':coeff,'proxy':proxy,'origin':origin,'bone':bone})
            joint_ids.append(bone);report['bones'].append({'name':hn[bone]['name'],'anchors':len(ids),'constraint_error':error,'max_absolute_weight_sum':float(np.abs(coeff).sum(1).max())})
    # Use anatomical axes for roll and scale; Reach and CE bones use different
    # local coordinate conventions. Wrist placement remains exact.
    jpos={n:np.array(m)[:3,3]@np.array(((0,1,0),(-1,0,0),(0,0,1))).T/3.048 for n,m in plate['bones'].items()}
    maps={}
    for side in ('l','r'):
        je=jpos[f'b_{side}_forearm'];jw=jpos[f'b_{side}_hand'];ce=hb[hi[f'frame {side} forearm'],:3,3];cw=hb[hi[f'frame {side} wriste'],:3,3]
        jwidth=np.array(plate['width_axes'][side]);cwidth=hb[hi[f'frame {side} index low'],:3,3]-hb[hi[f'frame {side} pinky low'],:3,3]
        axial=np.linalg.norm(cw-ce)/np.linalg.norm(jw-je);radial=np.linalg.norm(cwidth)/np.linalg.norm(jwidth)
        transform=basis(ce,cw,cwidth)@np.diag((axial,radial,radial))@basis(je,jw,jwidth).T
        maps[side]=(transform,jw,cw)
    verts=[];colors=[];bone_keys=[];local=[];component_names=[]
    for component in plate['components']:
        # Keep CE's articulated fingers and wrist seam; the Reach third-person
        # mitt and hand plate are too coarse for close-up finger animation.
        if component['component'] in ('arms-07:002','arms-07:003'):continue
        for face in component['faces']:
            for vi in face:
                name=max(component['weights'][vi],key=lambda a:a[1])[0];side=name[2];bi=('l','r').index(side)
                p=np.array(component['vertices'][vi])@np.array(((0,1,0),(-1,0,0),(0,0,1))).T/3.048
                transform,jw,cw=maps[side];p=transform@(p-jw)+cw
                coord=(p-bindings[bi]['origin'])/.08;affine=np.r_[1-coord.sum(),coord]
                verts.append([round(x*256) for x in position(p,(0,0,0))]);local.append(affine.tolist());bone_keys.append(bi);component_names.append(component['component'])
        colors.extend(np.rint(np.array(component['colors'])*255*.85).astype(int).tolist())
    mesh=indexed_mesh(verts,colors,[0]*len(verts),motion_keys=[(b,*np.round(c,7)) for b,c in zip(bone_keys,local)],color_tolerance=24)
    sources=mesh['sources'];rgba=lambda c:(c[0]<<24)|(c[1]<<16)|(c[2]<<8)|255
    xyz=lambda p:'{'+','.join(map(str,p))+'}';floats=lambda p:'{'+','.join(f'{float(v):.9g}f' if '.' in f'{float(v):.9g}' or 'e' in f'{float(v):.9g}' else f'{float(v):.1f}f' for v in p)+'}'
    lines=['/* Generated GUNGNIR viewmodel: source armor, shared CE animation cage. */','#include "gungnir_firstperson.h"']
    lines.append('static T3DVertPacked gungnir_fp_vertices[] __attribute__((aligned(16)))={')
    for a,b in zip(mesh['vertices'][::2],mesh['vertices'][1::2]):lines.append('{'+f'{xyz(a[0])},0,{xyz(b[0])},0,0x{rgba(a[1]):08x},0x{rgba(b[1]):08x},{{0,0}},{{0,0}}'+'},')
    lines.append('};');emit_batches(lines,'gungnir_fp',mesh)
    lines.append(f'const bg_model_asset bg_gungnir_fp_model={{gungnir_fp_vertices,{len(sources)},1.f,gungnir_fp_batches,gungnir_fp_indices,{len(mesh["batches"])},{len(verts)//3}}};')
    lines.append('const bg_gungnir_fp_vertex bg_gungnir_fp_vertices[]={'+','.join('{'+str(bone_keys[i])+','+floats(local[i])+'}' for i in sources)+'};')
    for bi,b in enumerate(bindings):lines.append(f'static const float coefficients_{bi}[4][{len(b["corners"])}]={{'+','.join(floats(c) for c in b['coeff'])+'};')
    refs=[];colorrefs=[];previews={};binding_data={'local':np.array([local[i] for i in sources]),'bones':np.array([bone_keys[i] for i in sources])}
    for bi,b in enumerate(bindings):binding_data[f'coeff_{bi}']=b['coeff']
    runtime=json.loads((A/'generated/firstperson-report.json').read_text());aliases=runtime.get('aliases',{})
    for name in reduced['weapons']:
        actual=aliases.get(name,name)
        if actual!=name:refs.append(refs[list(reduced['weapons']).index(actual)]);colorrefs.append(colorrefs[list(reduced['weapons']).index(actual)]);continue
        weapon=reduced['weapons'][name]
        if name in ('sniper','plasma_pistol','plasma_rifle'):weapon=split_details(weapon,name)[0]
        wm,clips,_=prepare_model(weapon,name);assert len(wm['vertices'])==runtime['vertices'][name],(name,len(wm['vertices']),runtime['vertices'][name])
        remap={};corner=0
        for first,count,off,n in wm['batches']:
            for j in wm['indices'][off:off+n]:remap[corner]=first+j;corner+=1
        frame_binds=[]
        for bi,b in enumerate(bindings):
            indices=[remap[c] for c in b['corners']];lines.append(f'static const uint16_t {name}_anchors_{bi}[]={xyz(indices)};')
            binding_data[f'{name}_indices_{bi}']=np.array(indices)
            frame_binds.append('{'+f'{name}_anchors_{bi},&coefficients_{bi}[0][0],{len(indices)}'+'}')
        lines.append(f'static const bg_gungnir_fp_frame {name}_frames[2]={{'+','.join(frame_binds)+'};');refs.append(name+'_frames')
        classes=[]
        for c in wm['sources']:
            if c>=weapon['hand_triangle_count']*3:classes.append(0);continue
            t=weapon['triangles'][c//3];ws=t['weights'][c%3];dominant=max(ws,key=lambda x:x[1])[0]
            classes.append(1 if t['material']==0 else 2 if 'forearm' in hn[dominant]['name'] or 'upperarm' in hn[dominant]['name'] else 3)
        lines.append(f'static const uint8_t {name}_colors[]={xyz(classes)};');colorrefs.append(name+'_colors')
        allposes=[];maxerr=0
        for cname,clip in weapon['clips'].items():
            for frame in clip['frames']:
                fp=np.array([position(p,(0,0,0)) for p in frame]);result=[]
                for bi,b in enumerate(bindings):result.append(b['coeff']@np.rint(fp[b['corners']]*256))
                result=np.array(result);posed=np.array([np.array(local[i])@result[bone_keys[i]] for i in sources]);assert np.isfinite(posed).all()
                allposes.append(posed)
        idle=np.array(allposes[0]);previews[name]={'positions':idle.tolist(),'triangles':[[first+j for j in wm['indices'][off+k:off+k+3]] for first,count,off,n in wm['batches'] for k in range(0,n,3)],'base_positions':np.rint(np.array([position(p,(0,0,0)) for p in clips['idle']['frames'][0]])*256).tolist(),'base_colors':[v[1] for v in wm['vertices']],'classes':classes}
        report['weapons'][name]={'source_vertices':len(wm['vertices']),'checked_core_frames':len(allposes),'maximum_coordinate':float(np.max(np.abs(allposes)))}
    lines.append('const bg_gungnir_fp_frame *const bg_gungnir_fp_frames[BG_FP_WEAPONS]={'+','.join(refs)+'};')
    lines.append('const uint8_t *const bg_gungnir_fp_colors[BG_FP_WEAPONS]={'+','.join(colorrefs)+'};')
    (GENERATED/'gungnir_firstperson_data.c').write_text('\n'.join(lines)+'\n')
    report.update(vertices=len(sources),triangles=len(verts)//3,source_sha256=hashlib.sha256((OUT/'firstperson-plates.json').read_bytes()).hexdigest())
    (OUT/'firstperson-report.json').write_text(json.dumps(report,indent=2)+'\n')
    np.savez_compressed(OUT/'firstperson-binding.npz',**binding_data)
    np.savez_compressed(OUT/'firstperson-preview.npz',triangles=np.array([[first+j for j in mesh['indices'][off+k:off+k+3]] for first,count,off,n in mesh['batches'] for k in range(0,n,3)]),colors=np.array([v[1] for v in mesh['vertices']]),**{n:np.array(v['positions']) for n,v in previews.items()})
    (OUT/'firstperson-base-preview.json').write_text(json.dumps(previews)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);args=p.parse_args();SOURCE=args.source;OUT=args.output;GENERATED=OUT;OUT.mkdir(parents=True,exist_ok=True);run()
